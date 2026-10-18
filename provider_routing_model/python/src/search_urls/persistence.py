"""Locked, append-only run artifacts with safe resume and crash recovery."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import ValidationError

from query_gold.io import atomic_write_bytes, ensure_safe_path, json_bytes
from search_urls.configuration import SearchConfig
from search_urls.models import (
    BenchmarkCase,
    CaseResultRecord,
    CostEvidence,
    parse_benchmark_case,
)

if TYPE_CHECKING:
    from search_urls.transport import AttemptContext

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _to_win_long_path(path: Path) -> Path:
    if sys.platform != "win32":
        return path
    s = os.path.abspath(str(path))
    if not s.startswith(("\\\\?\\", "//?/")):
        return Path(f"\\\\?\\{s}")
    return path


def load_benchmark(
    path: Path, *, input_bytes: bytes | None = None
) -> tuple[bytes, list[BenchmarkCase], str]:
    """Read and validate one explicitly selected public JSONL input exactly once."""
    _validate_public_input_path(path)
    try:
        safe_path = ensure_safe_path(path, require_existing=True)
        raw = input_bytes if input_bytes is not None else safe_path.read_bytes()
    except (OSError, ValueError):
        raise ValueError("cannot read public benchmark input") from None
    cases = _parse_cases(raw)
    return raw, cases, hashlib.sha256(raw).hexdigest()


def _validate_public_input_path(path: Path) -> None:
    for part in path.parts:
        lowered = part.casefold()
        if lowered == "answers" or "answer" in lowered:
            raise ValueError("reference answer paths are not public benchmark inputs")
        if lowered == ".env" or lowered.startswith(".env."):
            raise ValueError("credential paths are not benchmark inputs")


def _parse_cases(raw: bytes) -> list[BenchmarkCase]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("public benchmark input must be UTF-8 JSONL") from None
    cases: list[BenchmarkCase] = []
    seen: set[str] = set()
    for line in text.splitlines():
        if not line.strip():
            raise ValueError("public benchmark input contains a blank JSONL row")
        try:
            row = json.loads(line, parse_constant=_reject_constant)
        except (json.JSONDecodeError, ValueError):
            raise ValueError("public benchmark input contains invalid JSON") from None
        case = parse_benchmark_case(row)
        if case.case_id in seen:
            raise ValueError("public benchmark input contains duplicate case IDs")
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValueError("public benchmark input must contain at least one case")
    return cases


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value {value}")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_attempt_url(value: str) -> str:
    """Persist only the endpoint origin/path, never request parameters or fragments."""
    from urllib.parse import urlsplit, urlunsplit

    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
            return "[redacted-url]"
        return urlunsplit((parsed.scheme, parsed.hostname, parsed.path, "", ""))
    except ValueError:
        return "[redacted-url]"


class RunStore:
    """Own one run directory, exclusive lock, and fsynced JSONL journals."""

    def __init__(
        self,
        output_root: Path,
        run_id: str,
        config: SearchConfig,
        input_path: Path,
        *,
        input_bytes: bytes | None = None,
    ) -> None:
        if not _RUN_ID_PATTERN.fullmatch(run_id) or run_id in {".", ".."}:
            raise ValueError("run ID must be a safe path component")
        _validate_public_input_path(input_path)
        self.output_root = output_root
        self.run_id = run_id
        self.config = config
        self.input_path = input_path
        self.input_bytes, self.cases, self.dataset_sha256 = load_benchmark(
            input_path, input_bytes=input_bytes
        )
        self.config_bytes = json_bytes(config.model_dump(mode="json", by_alias=True))
        self.config_sha256 = _sha256(self.config_bytes)
        self.run_dir = self.output_root / run_id
        self.manifest_path = self.run_dir / "manifest.json"
        self.attempts_path = self.run_dir / "attempts.jsonl"
        self.results_path = self.run_dir / "results.jsonl"
        self.lock_path = self.run_dir / ".lock"
        self.inputs_dir = self.run_dir / "inputs"
        self._lock_stream: Any = None
        self._case_query_hash = {
            case.case_id: _sha256(case.query.encode("utf-8")) for case in self.cases
        }
        self._case_by_id = {case.case_id: case for case in self.cases}
        self._active_attempts: dict[str, dict[str, Any]] = {}
        self._attempt_rows: list[dict[str, Any]] = []
        self._result_rows: list[CaseResultRecord] = []
        self._manifest: dict[str, Any] = {}

    def __enter__(self) -> RunStore:
        safe_run_dir = ensure_safe_path(self.run_dir)
        safe_run_dir.mkdir(parents=True, exist_ok=True)
        ensure_safe_path(self.run_dir)
        ensure_safe_path(self.inputs_dir).mkdir(parents=True, exist_ok=True)
        self._acquire_lock()
        try:
            self._initialize_manifest()
            self._recover_logs()
            return self
        except BaseException:
            self._release_lock()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._release_lock()

    @property
    def manifest(self) -> dict[str, Any]:
        return dict(self._manifest)

    @property
    def input_snapshot_path(self) -> Path:
        return _to_win_long_path(self.inputs_dir / f"{self.dataset_sha256}.jsonl")

    def _acquire_lock(self) -> None:
        ensure_safe_path(self.lock_path)
        self._lock_stream = self.lock_path.open("a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                self._lock_stream.seek(0, os.SEEK_END)
                if self._lock_stream.tell() == 0:
                    self._lock_stream.write(b"\0")
                    self._lock_stream.flush()
                self._lock_stream.seek(0)
                msvcrt.locking(self._lock_stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError):
            self._lock_stream.close()
            self._lock_stream = None
            raise ValueError("run directory is already locked") from None

    def _release_lock(self) -> None:
        if self._lock_stream is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                self._lock_stream.seek(0)
                msvcrt.locking(self._lock_stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._lock_stream.fileno(), fcntl.LOCK_UN)
        finally:
            self._lock_stream.close()
            self._lock_stream = None

    def _initialize_manifest(self) -> None:
        manifest = self._read_manifest_if_present()
        if manifest is None:
            if self.attempts_path.exists() or self.results_path.exists():
                raise ValueError("run journals exist without a manifest")
            self.inputs_dir.mkdir(parents=True, exist_ok=True)
            self._write_input_snapshot()
            self._manifest = {
                "schemaVersion": "search-run-manifest/v1",
                "runId": self.run_id,
                "createdAt": _utc_now(),
                "updatedAt": _utc_now(),
                "config": json.loads(self.config_bytes),
                "configSHA256": self.config_sha256,
                "datasetSHA256": self.dataset_sha256,
                "runtimeSettings": {},
                "inputSnapshots": [self._snapshot_record()],
            }
            self._write_manifest()
            return

        if manifest.get("schemaVersion") != "search-run-manifest/v1":
            raise ValueError("unsupported run manifest")
        if manifest.get("runId") != self.run_id:
            raise ValueError("run manifest ID does not match directory")
        if manifest.get("configSHA256") != self.config_sha256:
            raise ValueError("run config changed; use a new run ID")
        if manifest.get("config") != json.loads(self.config_bytes):
            raise ValueError("run manifest config does not match its config hash")
        runtime_settings = manifest.get("runtimeSettings", {})
        if not isinstance(runtime_settings, dict) or (
            runtime_settings
            and (
                set(runtime_settings) != {"accessMode"}
                or runtime_settings.get("accessMode") not in {"keyed", "keyless"}
            )
        ):
            raise ValueError("invalid pinned runtime settings")
        previous_path, previous_bytes = self._active_snapshot(manifest)
        del previous_path
        previous_cases = _parse_cases(previous_bytes)
        previous_by_id = {case.case_id: case.query for case in previous_cases}
        current_by_id = {case.case_id: case.query for case in self.cases}
        if any(case_id not in current_by_id for case_id in previous_by_id):
            raise ValueError("resume input removed an existing case")
        if any(current_by_id[case_id] != query for case_id, query in previous_by_id.items()):
            raise ValueError("resume input changed an existing query")

        self._manifest = manifest
        if manifest.get("datasetSHA256") != self.dataset_sha256:
            self.inputs_dir.mkdir(parents=True, exist_ok=True)
            self._write_input_snapshot()
            snapshots = manifest.get("inputSnapshots")
            if not isinstance(snapshots, list):
                raise ValueError("invalid input snapshot manifest")
            if not any(item.get("sha256") == self.dataset_sha256 for item in snapshots):
                snapshots.append(self._snapshot_record())
            self._manifest["datasetSHA256"] = self.dataset_sha256
            self._manifest["updatedAt"] = _utc_now()
            self._write_manifest()

    def _snapshot_record(self) -> dict[str, Any]:
        return {
            "sha256": self.dataset_sha256,
            "path": f"inputs/{self.dataset_sha256}.jsonl",
            "caseCount": len(self.cases),
            "capturedAt": _utc_now(),
        }

    def pin_runtime_settings(self, settings: dict[str, str]) -> None:
        """Pin the nonsecret access mode used to make this run resumable safely."""
        if self._lock_stream is None:
            raise RuntimeError("runtime settings can only be pinned while the run is open")
        if set(settings) != {"accessMode"} or settings.get("accessMode") not in {
            "keyed",
            "keyless",
        }:
            raise ValueError("invalid pinned runtime settings")
        resolved = {"accessMode": settings["accessMode"]}
        existing = self._manifest.get("runtimeSettings", {})
        if not isinstance(existing, dict):
            raise ValueError("invalid pinned runtime settings")
        if existing:
            if existing != resolved:
                raise ValueError("provider access mode changed; use a new run ID")
            return
        self._manifest["runtimeSettings"] = resolved
        self._write_manifest()

    def _write_input_snapshot(self) -> None:
        path = self.input_snapshot_path
        ensure_safe_path(path)
        ensure_safe_path(path.parent).mkdir(parents=True, exist_ok=True)
        if path.exists():
            if _sha256(path.read_bytes()) != self.dataset_sha256:
                raise ValueError("input snapshot hash mismatch")
            return
        atomic_write_bytes(path, self.input_bytes)

    def _read_manifest_if_present(self) -> dict[str, Any] | None:
        if not self.manifest_path.exists():
            return None
        try:
            manifest_file = ensure_safe_path(self.manifest_path, require_existing=True)
            value = json.loads(manifest_file.read_text("utf-8"), parse_constant=_reject_constant)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("invalid run manifest") from None
        if not isinstance(value, dict):
            raise ValueError("invalid run manifest")
        return value

    def _active_snapshot(self, manifest: dict[str, Any]) -> tuple[Path, bytes]:
        snapshots = manifest.get("inputSnapshots")
        digest = manifest.get("datasetSHA256")
        if not isinstance(snapshots, list) or not isinstance(digest, str):
            raise ValueError("invalid input snapshot manifest")
        matching = [
            item for item in snapshots if isinstance(item, dict) and item.get("sha256") == digest
        ]
        if len(matching) != 1:
            raise ValueError("active input snapshot is missing or duplicated")
        relative = matching[0].get("path")
        if relative != f"inputs/{digest}.jsonl":
            raise ValueError("invalid input snapshot path")
        path = _to_win_long_path(self.run_dir / relative)
        try:
            content = ensure_safe_path(path, require_existing=True).read_bytes()
        except (OSError, ValueError):
            raise ValueError("active input snapshot is missing") from None
        if _sha256(content) != digest:
            raise ValueError("active input snapshot hash mismatch")
        return path, content

    def _write_manifest(self) -> None:
        self._manifest["updatedAt"] = _utc_now()
        atomic_write_bytes(self.manifest_path, json_bytes(self._manifest, pretty=True))

    def _recover_logs(self) -> None:
        self._attempt_rows = self._read_jsonl(self.attempts_path, expected="attempt")
        self._result_rows = self._read_jsonl(self.results_path, expected="result")
        self._active_attempts = {}
        for row in self._attempt_rows:
            event = row.get("event")
            if event == "cost":
                references = row.get("responseAttemptIds")
                started_ids = {
                    str(start.get("attemptId"))
                    for start in self._attempt_rows
                    if start.get("event") == "started"
                }
                if not isinstance(references, list) or any(
                    not isinstance(item, str) or item not in started_ids for item in references
                ):
                    raise ValueError("attempt cost event references an unknown attempt")
                continue
            attempt_id = row.get("attemptId")
            if not isinstance(attempt_id, str):
                raise ValueError("attempt journal row is missing an ID")
            if event == "started":
                if attempt_id in self._active_attempts:
                    raise ValueError("duplicate attempt start in journal")
                self._active_attempts[attempt_id] = row
            elif event == "finished":
                if attempt_id not in self._active_attempts:
                    raise ValueError("attempt finish has no start")
                del self._active_attempts[attempt_id]
            else:
                raise ValueError("invalid attempt journal event")
        for row in list(self._active_attempts.values()):
            self.finish_attempt(
                str(row["attemptId"]),
                status="cancelled",
                error_code="interrupted",
            )

    def _read_jsonl(self, path: Path, *, expected: str) -> list[Any]:
        if not path.exists():
            return []
        safe = ensure_safe_path(path, require_existing=True)
        raw = safe.read_bytes()
        if raw and not raw.endswith(b"\n"):
            last_newline = raw.rfind(b"\n")
            retained = raw[: last_newline + 1] if last_newline >= 0 else b""
            with safe.open("r+b") as stream:
                stream.truncate(len(retained))
                stream.flush()
                os.fsync(stream.fileno())
            raw = retained
        rows: list[Any] = []
        for index, line in enumerate(raw.splitlines(), start=1):
            try:
                row = json.loads(line, parse_constant=_reject_constant)
            except (json.JSONDecodeError, ValueError):
                raise ValueError(f"malformed terminated {expected} journal row {index}") from None
            if not isinstance(row, dict):
                raise ValueError(f"malformed terminated {expected} journal row {index}")
            if expected == "result":
                try:
                    result = CaseResultRecord.model_validate_json(line)
                except ValidationError:
                    raise ValueError(f"malformed terminated result journal row {index}") from None
                self._validate_result_case(result)
                rows.append(result)
            else:
                if row.get("runId") != self.run_id:
                    raise ValueError(f"malformed terminated attempt journal row {index}")
                rows.append(row)
        return rows

    def begin_attempt(
        self,
        context: AttemptContext,
        method: str,
        url: str,
        *,
        queue_latency_ms: int = 0,
    ) -> str:
        if context.case_id not in self._case_query_hash:
            raise ValueError("attempt references an unknown case")
        attempt_id = uuid4().hex
        count = self.request_count(context.case_id, context.repetition) + 1
        row: dict[str, Any] = {
            "event": "started",
            "attemptId": attempt_id,
            "runId": self.run_id,
            "datasetSha256": self.dataset_sha256,
            "configSha256": self.config_sha256,
            "caseId": context.case_id,
            "querySha256": self._case_query_hash[context.case_id],
            "repetition": context.repetition,
            "retry": context.retry,
            "requestNumber": count,
            "provider": context.provider,
            "method": method.upper(),
            "url": _safe_attempt_url(url),
            "startedAt": _utc_now(),
            "queueLatencyMs": max(0, queue_latency_ms),
            "costStatus": "unknown",
            "reportedUsd": None,
            "nativeUsage": None,
            "priceSnapshot": None,
        }
        self._append(self.attempts_path, row)
        self._attempt_rows.append(row)
        self._active_attempts[attempt_id] = row
        return attempt_id

    def finish_attempt(
        self,
        attempt_id: str,
        *,
        status: str,
        http_status: int | None = None,
        error_code: str | None = None,
        latency_ms: int | None = None,
        reported_usd: str | None = None,
        estimated_usd: str | None = None,
        source: str = "unknown",
        native_usage: object = None,
        price_snapshot: object = None,
        request_id: str | None = None,
    ) -> None:
        if status not in {"success", "error", "cancelled"}:
            raise ValueError("invalid physical attempt status")
        if source not in {"reported", "estimated", "unknown"}:
            raise ValueError("invalid physical attempt cost source")
        if reported_usd is not None and estimated_usd is not None:
            raise ValueError("reported and estimated attempt costs must remain separate")
        if source == "reported" and reported_usd is None:
            raise ValueError("reported attempt cost requires reportedUsd")
        if source == "estimated" and estimated_usd is None:
            raise ValueError("estimated attempt cost requires estimatedUsd")
        if attempt_id not in self._active_attempts:
            raise ValueError("attempt is not active")
        row: dict[str, Any] = {
            "event": "finished",
            "attemptId": attempt_id,
            "runId": self.run_id,
            "datasetSha256": self.dataset_sha256,
            "configSha256": self.config_sha256,
            "finishedAt": _utc_now(),
            "status": status,
            "httpStatus": http_status,
            "errorCode": error_code,
            "latencyMs": max(0, latency_ms) if latency_ms is not None else None,
            "costStatus": source,
            "reportedUsd": reported_usd,
            "estimatedUsd": estimated_usd,
            "nativeUsage": native_usage,
            "priceSnapshot": price_snapshot,
            "requestId": request_id,
        }
        self._append(self.attempts_path, row)
        self._attempt_rows.append(row)
        del self._active_attempts[attempt_id]

    def reconcile_attempt_costs(self, attempt_ids: list[str], evidence: CostEvidence) -> None:
        """Append adapter-normalized evidence once for a response and its attempts."""
        if not attempt_ids:
            return
        if len(set(attempt_ids)) != len(attempt_ids):
            raise ValueError("response cost references duplicate attempts")
        payload = evidence.model_dump(mode="json", by_alias=True)
        starts: list[dict[str, Any]] = []
        for attempt_id in attempt_ids:
            start = next(
                (
                    row
                    for row in self._attempt_rows
                    if row.get("event") == "started" and row.get("attemptId") == attempt_id
                ),
                None,
            )
            if start is None:
                raise ValueError("cost evidence references an unknown attempt")
            if any(
                attempt_id in event.get("responseAttemptIds", [])
                for event in self._attempt_rows
                if event.get("event") == "cost"
            ):
                raise ValueError("response attempt cost was already reconciled")
            finished = next(
                (
                    row
                    for row in reversed(self._attempt_rows)
                    if row.get("event") == "finished" and row.get("attemptId") == attempt_id
                ),
                None,
            )
            if finished is None or finished.get("status") != "success":
                raise ValueError("response cost requires successful physical attempts")
            starts.append(start)
        identities = {(start.get("caseId"), start.get("repetition")) for start in starts}
        if len(identities) != 1:
            raise ValueError("response cost attempts must belong to one logical query")
        row = {
            "event": "cost",
            "responseAttemptIds": list(attempt_ids),
            "runId": self.run_id,
            "datasetSha256": self.dataset_sha256,
            "configSha256": self.config_sha256,
            "source": payload["source"],
            "reportedUsd": payload["reportedUsd"],
            "estimatedUsd": payload["estimatedUsd"],
            "nativeUsage": payload["nativeUsage"],
            "priceSnapshot": payload["priceSnapshot"],
            "lineItems": payload["lineItems"],
            "totalUsd": payload["totalUsd"],
        }
        self._append(self.attempts_path, row)
        self._attempt_rows.append(row)

    def append_result(self, record: CaseResultRecord | dict[str, Any]) -> CaseResultRecord:
        if isinstance(record, CaseResultRecord):
            validated = record
        else:
            values = dict(record)
            values.setdefault("runId", self.run_id)
            values.setdefault("datasetSha256", self.dataset_sha256)
            values.setdefault("configSha256", self.config_sha256)
            try:
                validated = CaseResultRecord.model_validate(values)
            except ValidationError:
                raise ValueError("invalid case result record") from None
        if validated.run_id != self.run_id or validated.config_sha256 != self.config_sha256:
            raise ValueError("case result does not match this run")
        if validated.dataset_sha256 != self.dataset_sha256:
            raise ValueError("case result does not match the active input snapshot")
        self._validate_result_case(validated)
        self._append(self.results_path, validated.model_dump(mode="json", by_alias=True))
        self._result_rows.append(validated)
        return validated

    def _validate_result_case(self, result: CaseResultRecord) -> None:
        case = self._case_by_id.get(result.case_id)
        if case is None or result.query != case.query or result.provider != self.config.provider:
            raise ValueError("case result does not match this run's public input and provider")

    def _append(self, path: Path, value: object) -> None:
        ensure_safe_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        ensure_safe_path(path)
        with path.open("ab") as stream:
            stream.write(json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())

    def result_states(self) -> dict[tuple[str, int], CaseResultRecord]:
        """Return the latest terminal state for each case and repetition."""
        states: dict[tuple[str, int], CaseResultRecord] = {}
        for row in self._result_rows:
            states[(row.case_id, row.repetition)] = row
        return states

    def completed_ids(self, repetition: int = 0) -> set[str]:
        """Return IDs whose latest state in one repetition succeeded."""
        return {
            case_id
            for (case_id, row_repetition), row in self.result_states().items()
            if row_repetition == repetition and row.status == "success"
        }

    def request_count(self, case_id: str, repetition: int = 0) -> int:
        """Count every started physical request, including interrupted attempts."""
        return sum(
            1
            for row in self._attempt_rows
            if row.get("event") == "started"
            and row.get("caseId") == case_id
            and row.get("repetition") == repetition
        )

    def attempt_ids_for_case(self, case_id: str, repetition: int = 0) -> list[str]:
        return [
            str(row["attemptId"])
            for row in self._attempt_rows
            if row.get("event") == "started"
            and row.get("caseId") == case_id
            and row.get("repetition") == repetition
        ]
