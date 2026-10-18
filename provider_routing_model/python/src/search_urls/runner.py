"""Resumable, one-provider search collection orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from query_gold.io import json_bytes
from search_urls.configuration import SearchConfig, load_config
from search_urls.models import (
    BenchmarkCase,
    CaseResultRecord,
    SafeSearchError,
    SearchResponse,
)
from search_urls.persistence import RunStore
from search_urls.providers import SearchAdapter, create_adapter
from search_urls.transport import HttpxJsonTransport, SearchProviderError, utc_now_iso


def repository_root() -> Path:
    """Locate the repository independently of the caller's working directory."""
    return Path(__file__).resolve().parents[3]


def _config_sha256(config: SearchConfig) -> str:
    canonical = json_bytes(config.model_dump(mode="json", by_alias=True))
    return hashlib.sha256(canonical).hexdigest()


def _artifact_directory(path: Path) -> str:
    root = repository_root()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


@dataclass(frozen=True, slots=True)
class CaseSelection:
    """Pending work and resume counts fixed before provider construction."""

    cases: tuple[BenchmarkCase, ...]
    skipped_success: int
    skipped_error: int
    eligible: int
    deferred: int


def _select_cases(
    cases: list[BenchmarkCase],
    store: RunStore,
    *,
    retry_failed: bool,
    max_queries: int | None,
) -> CaseSelection:
    if max_queries is not None and max_queries < 1:
        raise ValueError("max queries must be positive")
    states = store.result_states()
    pending: list[BenchmarkCase] = []
    skipped_success = 0
    skipped_error = 0
    for case in cases:
        previous = states.get((case.case_id, 0))
        if previous is None or previous.status == "cancelled":
            pending.append(case)
        elif previous.status == "success":
            skipped_success += 1
        elif previous.status == "error" and retry_failed:
            pending.append(case)
        else:
            skipped_error += 1

    eligible = len(pending)
    selected = pending if max_queries is None else pending[:max_queries]
    return CaseSelection(
        cases=tuple(selected),
        skipped_success=skipped_success,
        skipped_error=skipped_error,
        eligible=eligible,
        deferred=eligible - len(selected),
    )


def _elapsed_label(seconds: float) -> str:
    whole = max(0, int(seconds))
    if whole < 60:
        return f"{whole}s"
    minutes, remaining = divmod(whole, 60)
    if minutes < 60:
        return f"{minutes}m{remaining:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


class _ProgressReporter:
    """Compact stderr progress with ETA and a low-frequency heartbeat."""

    def __init__(self, total: int, *, enabled: bool, stream: TextIO) -> None:
        self.total = total
        self.enabled = enabled and total > 0
        self.stream = stream
        self.started = time.monotonic()
        self.completed = 0
        self.counts = {"success": 0, "error": 0, "cancelled": 0}
        self._is_tty = bool(getattr(stream, "isatty", lambda: False)())
        self._last_plain_update = self.started

    def update(self, status: str) -> None:
        self.completed += 1
        self.counts[status] += 1
        self._emit(final=self.completed >= self.total)

    async def heartbeat(self, stop: asyncio.Event) -> None:
        if not self.enabled:
            return
        interval = 1.0 if self._is_tty else 15.0
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                if self._is_tty or time.monotonic() - self._last_plain_update >= 15.0:
                    self._emit()

    def finish(self) -> None:
        if self.enabled:
            self._emit(final=True)

    def _emit(self, *, final: bool = False) -> None:
        if not self.enabled:
            return
        elapsed = time.monotonic() - self.started
        percent = int(100 * self.completed / self.total)
        filled = min(20, int(20 * self.completed / self.total))
        bar = "#" * filled + "-" * (20 - filled)
        remaining = max(0, self.total - self.completed)
        eta = "--" if self.completed == 0 else _elapsed_label(elapsed * remaining / self.completed)
        line = (
            f"Search URLs [{bar}] {self.completed}/{self.total} {percent}% | "
            f"ok {self.counts['success']} | error {self.counts['error']} | "
            f"cancelled {self.counts['cancelled']} | elapsed {_elapsed_label(elapsed)} | "
            f"ETA {eta}"
        )
        if self._is_tty:
            self.stream.write("\r" + line + ("\n" if final else ""))
        else:
            self.stream.write(line + "\n")
        self.stream.flush()
        self._last_plain_update = time.monotonic()


class SearchCollectionRunner:
    """Run selected queries through one adapter with durable, retry-aware results."""

    def __init__(
        self,
        config: SearchConfig,
        store: RunStore,
        adapter: SearchAdapter,
        transport: HttpxJsonTransport,
        *,
        invocation_id: str,
        progress: bool = True,
        progress_stream: TextIO | None = None,
        fresh_request_budget: bool = False,
    ) -> None:
        self.config = config
        self.fresh_request_budget = fresh_request_budget
        self.store = store
        self.adapter = adapter
        self.transport = transport
        self.invocation_id = invocation_id
        self.progress_enabled = progress
        self.progress_stream = progress_stream
        self._physical_attempts = 0

    async def run(self, selection: CaseSelection) -> dict[str, object]:
        if not selection.cases:
            return self._summary(selection, interrupted=False, reporter=None)

        reporter = _ProgressReporter(
            len(selection.cases),
            enabled=self.progress_enabled,
            stream=self.progress_stream or sys.stderr,
        )
        reporter._emit()
        heartbeat_stop = asyncio.Event()
        heartbeat = asyncio.create_task(reporter.heartbeat(heartbeat_stop))
        # Queued cases start their query deadline only once a dispatch slot is free.
        slots = asyncio.Semaphore(self.config.max_concurrency)

        async def dispatch(case: BenchmarkCase) -> None:
            async with slots:
                await self._run_case(case, reporter)

        tasks = [asyncio.create_task(dispatch(case)) for case in selection.cases]
        interrupted = False
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            interrupted = True
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        finally:
            heartbeat_stop.set()
            await heartbeat
            reporter.finish()
        return self._summary(selection, interrupted=interrupted, reporter=reporter)

    async def _run_case(self, case: BenchmarkCase, reporter: _ProgressReporter) -> None:
        started = time.monotonic()
        started_at = utc_now_iso()
        deadline = started + self.config.limits.query_timeout_ms / 1000
        attempt_ids: list[str] = []
        response_attempt_ids: list[str] = []
        response: SearchResponse | None = None
        last_error: SearchProviderError | None = None
        progress_status = "error"
        max_retries = self.config.limits.max_retries
        # --retry-failed caps physical requests per invocation; the journal keeps all attempts.
        baseline = self.store.request_count(case.case_id, 0) if self.fresh_request_budget else 0

        try:
            for retry in range(max_retries + 1):
                scoped = self.transport.for_query(
                    case.case_id,
                    0,
                    retry,
                    self.config.limits.max_requests_per_query,
                    deadline,
                    self.store.request_count(case.case_id, 0) - baseline,
                )
                try:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    async with asyncio.timeout(remaining):
                        response = await self.adapter.search(case.query, scoped)
                    if response.query != case.query or response.provider != self.config.provider:
                        raise SearchProviderError(
                            self.config.provider,
                            "invalid_response",
                            status_code=200,
                            retryable=True,
                        )
                except asyncio.CancelledError:
                    scoped.finish_query("cancelled", "cancelled")
                    attempt_ids.extend(scoped.attempt_ids)
                    progress_status = "cancelled"
                    self._record(
                        case,
                        started_at=started_at,
                        started=started,
                        status="cancelled",
                        response=None,
                        error=None,
                        attempt_ids=attempt_ids,
                        response_attempt_ids=[],
                    )
                    raise
                except SearchProviderError as error:
                    scoped.finish_query("error", error.code)
                    attempt_ids.extend(scoped.attempt_ids)
                    last_error = error
                    if self._can_retry(error, retry, max_retries, deadline):
                        continue
                    break
                except TimeoutError:
                    scoped.finish_query("error", "query_timeout")
                    attempt_ids.extend(scoped.attempt_ids)
                    last_error = SearchProviderError(
                        self.config.provider,
                        "query_timeout",
                        retryable=False,
                    )
                    break
                except ValidationError:
                    scoped.finish_query("error", "invalid_response")
                    attempt_ids.extend(scoped.attempt_ids)
                    last_error = SearchProviderError(
                        self.config.provider,
                        "invalid_response",
                        status_code=200,
                        retryable=True,
                    )
                    if self._can_retry(last_error, retry, max_retries, deadline):
                        continue
                    break
                except Exception:
                    scoped.finish_query("error", "internal_error")
                    attempt_ids.extend(scoped.attempt_ids)
                    self._record(
                        case,
                        started_at=started_at,
                        started=started,
                        status="error",
                        response=None,
                        error=SafeSearchError(code="internal_error", retryable=False),
                        attempt_ids=attempt_ids,
                        response_attempt_ids=[],
                    )
                    raise
                else:
                    scoped.finish_query("success")
                    attempt_ids.extend(scoped.attempt_ids)
                    response_attempt_ids = list(scoped.attempt_ids)
                    if response_attempt_ids:
                        self.store.reconcile_attempt_costs(response_attempt_ids, response.cost)
                    last_error = None
                    break

            status: Literal["success", "error", "cancelled"]
            if response is not None and last_error is None:
                progress_status = "success"
                safe_error = None
                status = "success"
            else:
                progress_status = "error"
                status = "error"
                if last_error is None:
                    last_error = SearchProviderError(
                        self.config.provider,
                        "provider_error",
                        retryable=False,
                    )
                safe_error = SafeSearchError(
                    code=last_error.code,
                    status_code=last_error.status_code,
                    retryable=last_error.retryable,
                )
            self._record(
                case,
                started_at=started_at,
                started=started,
                status=status,
                response=response if status == "success" else None,
                error=safe_error,
                attempt_ids=attempt_ids,
                response_attempt_ids=response_attempt_ids,
            )
        finally:
            reporter.update(progress_status)
            self._physical_attempts += len(attempt_ids)

    def _can_retry(
        self,
        error: SearchProviderError,
        retry: int,
        max_retries: int,
        deadline: float,
    ) -> bool:
        if retry >= max_retries or time.monotonic() >= deadline:
            return False
        if error.code in {"request_limit", "query_timeout"}:
            return False
        delay = error.retry_after_seconds
        if delay is not None and delay > 0:
            remaining = deadline - time.monotonic()
            if remaining <= delay:
                return False
        return True

    def _record(
        self,
        case: BenchmarkCase,
        *,
        started_at: str,
        started: float,
        status: Literal["success", "error", "cancelled"],
        response: SearchResponse | None,
        error: SafeSearchError | None,
        attempt_ids: list[str],
        response_attempt_ids: list[str],
    ) -> None:
        record = CaseResultRecord(
            run_id=self.store.run_id,
            dataset_sha256=self.store.dataset_sha256,
            config_sha256=self.store.config_sha256,
            case_id=case.case_id,
            query=case.query,
            query_sha256=hashlib.sha256(case.query.encode("utf-8")).hexdigest(),
            repetition=0,
            provider=self.config.provider,
            status=status,
            started_at=started_at,
            finished_at=utc_now_iso(),
            invocation_id=self.invocation_id,
            client_latency_ms=max(0, round((time.monotonic() - started) * 1000)),
            provider_reported_latency_ms=(
                response.provider_reported_latency_ms if response is not None else None
            ),
            response=response,
            error=error,
            attempt_ids=attempt_ids,
            response_attempt_ids=response_attempt_ids,
            cost_scope=(
                "response" if response_attempt_ids else "attempts" if attempt_ids else "unknown"
            ),
        )
        self.store.append_result(record)

    def _summary(
        self,
        selection: CaseSelection,
        *,
        interrupted: bool,
        reporter: _ProgressReporter | None,
    ) -> dict[str, object]:
        outcomes = (
            reporter.counts
            if reporter is not None
            else {
                "success": 0,
                "error": 0,
                "cancelled": 0,
            }
        )
        completed = reporter.completed if reporter is not None else 0
        return {
            "status": "interrupted" if interrupted else "completed",
            "provider": self.config.provider,
            "configSHA256": self.store.config_sha256,
            "datasetSHA256": self.store.dataset_sha256,
            "directory": _artifact_directory(self.store.run_dir),
            "inputCases": len(self.store.cases),
            "eligible": selection.eligible,
            "selected": len(selection.cases),
            "deferred": selection.deferred,
            "skippedSuccess": selection.skipped_success,
            "skippedError": selection.skipped_error,
            "success": outcomes["success"],
            "error": outcomes["error"],
            "cancelled": outcomes["cancelled"],
            "remaining": max(0, len(selection.cases) - completed),
            "physicalAttempts": self._physical_attempts,
        }


def _empty_summary(
    config: SearchConfig,
    store: RunStore,
    selection: CaseSelection,
) -> dict[str, object]:
    return {
        "status": "completed",
        "provider": config.provider,
        "configSHA256": store.config_sha256,
        "datasetSHA256": store.dataset_sha256,
        "directory": _artifact_directory(store.run_dir),
        "inputCases": len(store.cases),
        "eligible": selection.eligible,
        "selected": 0,
        "deferred": selection.deferred,
        "skippedSuccess": selection.skipped_success,
        "skippedError": selection.skipped_error,
        "success": 0,
        "error": 0,
        "cancelled": 0,
        "remaining": 0,
        "physicalAttempts": 0,
    }


async def run_collection(
    *,
    config_path: Path,
    benchmark_path: Path,
    env_file: Path | None = None,
    max_queries: int | None = None,
    retry_failed: bool = False,
    progress: bool = True,
    progress_stream: TextIO | None = None,
) -> dict[str, object]:
    """Load exact public input, resume it, then execute only pending searches."""
    if max_queries is not None and max_queries < 1:
        raise ValueError("max queries must be positive")
    root = repository_root()
    config = load_config(config_path)
    run_id = _config_sha256(config)
    output_root = root / "benchmarks" / "eval_v2" / "search_results" / config.provider
    with RunStore(output_root, run_id, config, benchmark_path) as store:
        selection = _select_cases(
            store.cases,
            store,
            retry_failed=retry_failed,
            max_queries=max_queries,
        )
        if not selection.cases:
            return _empty_summary(config, store, selection)

        credential_file = env_file if env_file is not None else root / ".env"
        if credential_file.is_file():
            load_dotenv(dotenv_path=credential_file, override=False)
        adapter = create_adapter(config)
        if config.provider in {"tavily", "keenable"}:
            key_attribute = "key" if config.provider == "tavily" else "api_key"
            resolved_key = getattr(adapter, key_attribute, None)
            access_mode = (
                "keyed"
                if isinstance(resolved_key, str) and bool(resolved_key.strip())
                else "keyless"
            )
            store.pin_runtime_settings({"accessMode": access_mode})
        invocation_id = uuid4().hex
        rate_limits = [(item.requests, item.window_ms) for item in config.rate_limits]
        async with httpx.AsyncClient(follow_redirects=False) as client:
            transport = HttpxJsonTransport(
                client,
                config.provider,
                journal=store,
                request_timeout_ms=config.limits.request_timeout_ms,
                rate_limits=rate_limits,
                max_concurrency=config.max_concurrency,
            )
            runner = SearchCollectionRunner(
                config,
                store,
                adapter,
                transport,
                invocation_id=invocation_id,
                progress=progress,
                progress_stream=progress_stream,
                fresh_request_budget=retry_failed,
            )
            return await runner.run(selection)
