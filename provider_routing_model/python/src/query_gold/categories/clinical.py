"""Curate version-anchored clinical-trial registry questions from ClinicalTrials.gov."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from query_gold.io import ensure_safe_path

CATEGORY_ID = "02_biomedical_clinical_trials"
SCHEMA_VERSION = "query-gold/v1"
GENERATOR_VERSION = "query-gold/v1"
SOURCE_FAMILY = "clinicaltrials_gov_registry"
API_STUDY_URL = "https://clinicaltrials.gov/api/v2/studies/"
PUBLIC_STUDY_URL = "https://clinicaltrials.gov/study/"
MAX_PHYSICAL_REQUESTS = 150
MAX_RETRIES = 1
USER_AGENT = "query-gold-clinical-curation/1.0 (public registry data)"


@dataclass(frozen=True)
class TrialSeed:
    """One pinned registry record and the secondary fact asked about it."""

    nct_id: str
    condition_query: str
    overall_status: str
    secondary_question: str


# The source searches are retained in raw/search/ and raw/search-active/. These
# IDs were selected from those cached official API responses, not from a QA set.
TRIALS: tuple[TrialSeed, ...] = (
    TrialSeed("NCT06304857", "breast cancer", "RECRUITING", "overall_completion_date"),
    TrialSeed("NCT04516057", "Alzheimer disease", "RECRUITING", "overall_completion_date"),
    TrialSeed("NCT07645924", "migraine", "RECRUITING", "overall_completion_date"),
    TrialSeed("NCT06296745", "lung cancer", "RECRUITING", "overall_completion_date"),
    TrialSeed("NCT05583721", "sickle cell disease", "RECRUITING", "overall_completion_date"),
    TrialSeed("NCT05418010", "multiple sclerosis", "RECRUITING", "overall_completion_date"),
    TrialSeed("NCT00884507", "Alzheimer disease", "COMPLETED", "registry_phase"),
    TrialSeed("NCT01842607", "asthma", "COMPLETED", "overall_completion_date"),
    TrialSeed("NCT01595841", "chronic kidney disease", "COMPLETED", "overall_completion_date"),
    TrialSeed("NCT03654274", "endometriosis", "COMPLETED", "registry_phase"),
    TrialSeed("NCT01713777", "epilepsy", "COMPLETED", "registry_phase"),
    TrialSeed("NCT00236756", "epilepsy", "COMPLETED", "registry_phase"),
    TrialSeed("NCT04737265", "heart failure", "COMPLETED", "overall_completion_date"),
    TrialSeed("NCT01270802", "HIV infection", "COMPLETED", "overall_completion_date"),
    TrialSeed("NCT02442700", "HIV infection", "COMPLETED", "registry_phase"),
    TrialSeed("NCT03470441", "myocardial infarction", "COMPLETED", "overall_completion_date"),
    TrialSeed("NCT00677053", "myocardial infarction", "COMPLETED", "registry_phase"),
    TrialSeed("NCT01688739", "migraine", "COMPLETED", "registry_phase"),
    TrialSeed("NCT01859481", "migraine", "COMPLETED", "overall_completion_date"),
    TrialSeed("NCT01490502", "multiple sclerosis", "COMPLETED", "overall_completion_date"),
    TrialSeed("NCT01332019", "multiple sclerosis", "COMPLETED", "registry_phase"),
    TrialSeed("NCT00004054", "prostate cancer", "COMPLETED", "registry_phase"),
    TrialSeed("NCT03890302", "rheumatoid arthritis", "COMPLETED", "registry_phase"),
    TrialSeed("NCT03926819", "sickle cell disease", "COMPLETED", "registry_phase"),
    TrialSeed("NCT00303381", "ulcerative colitis", "COMPLETED", "registry_phase"),
)

_DATE_FORMATS = (
    (re.compile(r"^\d{4}$"), "year"),
    (re.compile(r"^\d{4}-\d{2}$"), "month"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "day"),
)
_PHASE_VALUES = {"EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA"}
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_utc_timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an explicit UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO timestamp") from error
    if parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")
    if "T" not in value or not value.endswith(("Z", "+00:00")):
        raise ValueError(f"{field} must include a timezone-qualified date and time")
    return value.replace("+00:00", "Z")


def _parse_source_date(value: Any, field: str) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a source-supplied ISO date")
    for pattern, precision in _DATE_FORMATS:
        if pattern.fullmatch(value):
            try:
                if precision == "year":
                    if not 1 <= int(value) <= 9999:
                        raise ValueError("year out of range")
                elif precision == "month":
                    date.fromisoformat(f"{value}-01")
                else:
                    date.fromisoformat(value)
            except ValueError as error:
                raise ValueError(f"{field} is not a valid ISO {precision} date") from error
            return value, precision
    raise ValueError(f"{field} must retain YYYY, YYYY-MM, or YYYY-MM-DD precision")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant {value} is not allowed")


def _skip_space(text: str, offset: int) -> int:
    while offset < len(text) and text[offset] in " \t\r\n":
        offset += 1
    return offset


def _string_end(text: str, offset: int) -> int:
    if offset >= len(text) or text[offset] != '"':
        raise ValueError("invalid JSON string span")
    offset += 1
    while offset < len(text):
        character = text[offset]
        if character == "\\":
            offset += 2
        elif character == '"':
            return offset + 1
        else:
            offset += 1
    raise ValueError("unterminated JSON string")


def _skip_object(text: str, offset: int) -> int:
    cursor = _skip_space(text, offset + 1)
    if cursor < len(text) and text[cursor] == "}":
        return cursor + 1
    while cursor < len(text):
        key_end = _string_end(text, cursor)
        cursor = _skip_space(text, key_end)
        if cursor >= len(text) or text[cursor] != ":":
            raise ValueError("invalid JSON object member")
        cursor = _skip_value(text, cursor + 1)
        cursor = _skip_space(text, cursor)
        if cursor < len(text) and text[cursor] == "}":
            return cursor + 1
        if cursor >= len(text) or text[cursor] != ",":
            raise ValueError("invalid JSON object separator")
        cursor = _skip_space(text, cursor + 1)
    raise ValueError("unterminated JSON object")


def _skip_array(text: str, offset: int) -> int:
    cursor = _skip_space(text, offset + 1)
    if cursor < len(text) and text[cursor] == "]":
        return cursor + 1
    while cursor < len(text):
        cursor = _skip_value(text, cursor)
        cursor = _skip_space(text, cursor)
        if cursor < len(text) and text[cursor] == "]":
            return cursor + 1
        if cursor >= len(text) or text[cursor] != ",":
            raise ValueError("invalid JSON array separator")
        cursor = _skip_space(text, cursor + 1)
    raise ValueError("unterminated JSON array")


def _skip_value(text: str, offset: int) -> int:
    """Return the end of one JSON value without decoding or rewriting its bytes."""
    offset = _skip_space(text, offset)
    if offset >= len(text):
        raise ValueError("missing JSON value")
    if text[offset] == '"':
        return _string_end(text, offset)
    if text[offset] == "{":
        return _skip_object(text, offset)
    if text[offset] == "[":
        return _skip_array(text, offset)
    cursor = offset
    while cursor < len(text) and text[cursor] not in ",]} \t\r\n":
        cursor += 1
    if cursor == offset:
        raise ValueError("invalid JSON primitive")
    return cursor


def _object_member(text: str, offset: int, member_name: str) -> tuple[int, int, int]:
    cursor = _skip_space(text, offset)
    if text[cursor : cursor + 1] != "{":
        raise ValueError(f"JSON path expected object member {member_name!r}")
    cursor = _skip_space(text, cursor + 1)
    while cursor < len(text) and text[cursor] != "}":
        key_start = cursor
        key_end = _string_end(text, cursor)
        current_key = json.loads(text[key_start:key_end])
        value_start = _skip_space(text, key_end)
        if value_start >= len(text) or text[value_start] != ":":
            raise ValueError("invalid JSON object member")
        value_start = _skip_space(text, value_start + 1)
        value_end = _skip_value(text, value_start)
        if current_key == member_name:
            return key_start, value_start, value_end
        cursor = _skip_space(text, value_end)
        if cursor < len(text) and text[cursor] == ",":
            cursor = _skip_space(text, cursor + 1)
    raise ValueError(f"JSON object path member {member_name!r} is missing")


def _array_item(text: str, offset: int, item_index: int) -> tuple[int, int]:
    cursor = _skip_space(text, offset)
    if text[cursor : cursor + 1] != "[":
        raise ValueError(f"JSON path expected array index {item_index}")
    cursor = _skip_space(text, cursor + 1)
    current_index = 0
    while cursor < len(text) and text[cursor] != "]":
        item_start = cursor
        item_end = _skip_value(text, item_start)
        if current_index == item_index:
            return item_start, item_end
        current_index += 1
        cursor = _skip_space(text, item_end)
        if cursor < len(text) and text[cursor] == ",":
            cursor = _skip_space(text, cursor + 1)
    raise ValueError(f"JSON array index {item_index} is missing")


def _locate_member(text: str, path: tuple[str | int, ...]) -> tuple[int, int, int]:
    """Locate a JSON path, returning member-key start and value bounds if keyed."""
    if not path:
        raise ValueError("JSON path must not be empty")
    cursor = _skip_space(text, 0)
    for index, component in enumerate(path):
        is_last = index == len(path) - 1
        if isinstance(component, str):
            key_start, value_start, value_end = _object_member(text, cursor, component)
            if is_last:
                return key_start, value_start, value_end
            cursor = value_start
        else:
            item_start, item_end = _array_item(text, cursor, component)
            if is_last:
                return item_start, item_start, item_end
            cursor = item_start
    raise ValueError("JSON path did not resolve")


def _path_excerpt(text: str, path: tuple[str | int, ...]) -> str:
    start, _value_start, value_end = _locate_member(text, path)
    return text[start:value_end]


def _outcome_excerpt(text: str, outcomes_path: tuple[str | int, ...], outcome_index: int) -> str:
    key_start, _array_start, _array_end = _locate_member(text, outcomes_path)
    _item_start, _unused_start, item_end = _locate_member(text, (*outcomes_path, outcome_index))
    excerpt = text[key_start:item_end]
    if len(excerpt) <= 8000:
        return excerpt
    return _path_excerpt(text, (*outcomes_path, outcome_index, "measure"))


def _study_path(payload: dict[str, Any], nct_id: str) -> tuple[str | int, ...]:
    protocol = payload.get("protocolSection")
    identity = protocol.get("identificationModule") if isinstance(protocol, dict) else None
    if isinstance(identity, dict) and identity.get("nctId") == nct_id:
        return ()
    raise ValueError(f"ClinicalTrials.gov payload does not contain requested record {nct_id}")


def _record_sections(
    payload: dict[str, Any], nct_id: str
) -> tuple[dict[str, Any], tuple[str | int, ...]]:
    root = _study_path(payload, nct_id)
    study: Any = payload
    for component in root:
        study = study[component]
    if not isinstance(study, dict):
        raise ValueError(f"ClinicalTrials.gov record {nct_id} is not an object")
    protocol = study.get("protocolSection")
    if not isinstance(protocol, dict):
        raise ValueError(f"ClinicalTrials.gov record {nct_id} has no protocolSection")
    identity = protocol.get("identificationModule")
    if not isinstance(identity, dict) or identity.get("nctId") != nct_id:
        raise ValueError(f"ClinicalTrials.gov record identity does not match {nct_id}")
    status = protocol.get("statusModule")
    design = protocol.get("designModule")
    outcomes = protocol.get("outcomesModule")
    if (
        not isinstance(status, dict)
        or not isinstance(design, dict)
        or not isinstance(outcomes, dict)
    ):
        raise ValueError(f"ClinicalTrials.gov record {nct_id} is missing required modules")
    if status.get("overallStatus") not in {"COMPLETED", "RECRUITING"}:
        raise ValueError(f"ClinicalTrials.gov record {nct_id} has an unexpected overall status")
    return study, root


def _phase_values(design: dict[str, Any]) -> list[str]:
    phases = design.get("phases")
    if not isinstance(phases, list) or not phases:
        raise ValueError("designModule.phases must be a non-empty registry list")
    if any(not isinstance(phase, str) or phase not in _PHASE_VALUES for phase in phases):
        raise ValueError("designModule.phases contains an unknown registry phase")
    return phases


def _phase_answer(phases: list[str]) -> str:
    if phases == ["NA"]:
        return "Not Applicable"
    if "NA" in phases:
        raise ValueError("designModule.phases must not combine NA with a numbered phase")
    labels = [
        "Early Phase 1" if phase == "EARLY_PHASE1" else f"Phase {phase[-1]}" for phase in phases
    ]
    return " and ".join(labels)


def _primary_measure(outcomes: dict[str, Any]) -> str:
    primary = outcomes.get("primaryOutcomes")
    if not isinstance(primary, list) or not primary:
        raise ValueError("outcomesModule.primaryOutcomes must have at least one measure")
    first = primary[0]
    measure = first.get("measure") if isinstance(first, dict) else None
    if not isinstance(measure, str) or not measure.strip():
        raise ValueError("the first primary outcome must contain a non-empty measure field")
    return measure.strip()


def _completion(status: dict[str, Any]) -> tuple[str, str, str]:
    """Read only overall completionDateStruct, preserving date precision and type."""
    completion = status.get("completionDateStruct")
    if not isinstance(completion, dict):
        raise ValueError("statusModule.completionDateStruct (overall completion) is missing")
    source_date, precision = _parse_source_date(
        completion.get("date"), "statusModule.completionDateStruct.date"
    )
    completion_type = completion.get("type")
    if completion_type not in {"ACTUAL", "ESTIMATED"}:
        raise ValueError("completionDateStruct.type must be ACTUAL or ESTIMATED")
    label = "Actual" if completion_type == "ACTUAL" else "Estimated"
    return source_date, precision, label


def _update_date(status: dict[str, Any]) -> tuple[str, str]:
    update = status.get("lastUpdatePostDateStruct")
    if not isinstance(update, dict):
        raise ValueError("statusModule.lastUpdatePostDateStruct is missing")
    return _parse_source_date(update.get("date"), "lastUpdatePostDateStruct.date")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path = ensure_safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path = ensure_safe_path(path)
    with path.open("a", encoding="utf-8", newline="") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()


def _physical_request_count(output_dir: Path) -> int:
    output_dir = _preflight_output_dir(output_dir)
    count = 0
    for name in ("discovery-requests.jsonl", "precollection-probes.jsonl", "requests.jsonl"):
        path = ensure_safe_path(output_dir / "raw" / name)
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as stream:
                count += sum(1 for line in stream if line.strip())
        except (OSError, UnicodeDecodeError) as error:
            raise RuntimeError(
                f"Cannot safely count prior public requests in {path.name}"
            ) from error
    return count


def _append_rejection(
    output_dir: Path, seed: TrialSeed, reason: str, status_code: int | None = None
) -> None:
    _append_jsonl(
        output_dir / "raw" / "rejected.jsonl",
        {
            "sourceRecordId": seed.nct_id,
            "url": f"{API_STUDY_URL}{seed.nct_id}",
            "status": status_code,
            "reason": reason,
        },
    )


def _cached_record_file(
    output_dir: Path, seed: TrialSeed
) -> tuple[bytes, dict[str, Any], str, str] | None:
    output_dir = _preflight_output_dir(output_dir)
    raw_path = output_dir / "raw" / "studies" / f"{seed.nct_id}.json"
    meta_path = output_dir / "raw" / "studies" / f"{seed.nct_id}.meta.json"
    raw_path = ensure_safe_path(raw_path)
    meta_path = ensure_safe_path(meta_path)
    if not raw_path.is_file() or not meta_path.is_file():
        return None
    try:
        body = raw_path.read_bytes()
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        payload = json.loads(
            body.decode("utf-8", errors="strict"), parse_constant=_reject_json_constant
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _append_rejection(output_dir, seed, "cached study API payload or metadata is invalid")
        raise ValueError(
            f"Cached ClinicalTrials.gov study payload for {seed.nct_id} is invalid"
        ) from None
    if not isinstance(metadata, dict):
        _append_rejection(output_dir, seed, "cached study API metadata is not an object")
        raise ValueError(f"Cached ClinicalTrials.gov metadata for {seed.nct_id} is invalid")
    if not isinstance(payload, dict):
        _append_rejection(output_dir, seed, "cached study API payload is not a JSON object")
        raise ValueError(f"Cached ClinicalTrials.gov study payload for {seed.nct_id} is invalid")
    digest = hashlib.sha256(body).hexdigest()
    if metadata.get("rawSha256") != digest or not isinstance(metadata.get("retrievedAtUTC"), str):
        _append_rejection(
            output_dir, seed, "cached study API payload metadata checksum/timestamp mismatch"
        )
        raise ValueError(
            f"Cached ClinicalTrials.gov study payload for {seed.nct_id} failed its cache check"
        )
    retrieval_time = _validate_utc_timestamp(metadata["retrievedAtUTC"], "retrievedAtUTC")
    if metadata.get("url") != f"{API_STUDY_URL}{seed.nct_id}":
        _append_rejection(output_dir, seed, "cached study API metadata URL mismatch")
        raise ValueError(
            f"Cached ClinicalTrials.gov metadata for {seed.nct_id} failed its URL check"
        )
    return body, payload, retrieval_time, raw_path.relative_to(output_dir).as_posix()


def _fetch_record(
    output_dir: Path, seed: TrialSeed, client: httpx.Client
) -> tuple[bytes, dict[str, Any], str, str]:
    output_dir = _preflight_output_dir(output_dir)
    cached = _cached_record_file(output_dir, seed)
    if cached is not None:
        return cached
    url = f"{API_STUDY_URL}{seed.nct_id}"
    raw_path = output_dir / "raw" / "studies" / f"{seed.nct_id}.json"
    meta_path = output_dir / "raw" / "studies" / f"{seed.nct_id}.meta.json"
    raw_path = ensure_safe_path(raw_path)
    meta_path = ensure_safe_path(meta_path)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir = _preflight_output_dir(output_dir)
    raw_path = ensure_safe_path(raw_path)
    meta_path = ensure_safe_path(meta_path)
    for attempt in range(MAX_RETRIES + 1):
        if _physical_request_count(output_dir) >= MAX_PHYSICAL_REQUESTS:
            _append_rejection(output_dir, seed, "150-request physical network cap reached")
            raise RuntimeError("ClinicalTrials.gov collection reached the 150-request cap")
        retrieved_at = _utc_now()
        try:
            response = client.get(url)
            status_code = response.status_code
            if status_code == 200:
                body = response.content
                _append_jsonl(
                    output_dir / "raw" / "requests.jsonl",
                    {
                        "url": url,
                        "attempt": attempt + 1,
                        "retrievedAtUTC": retrieved_at,
                        "status": status_code,
                        "responseBytes": len(body),
                    },
                )
                # Preserve the exact API payload before parsing or deriving facts.
                raw_path = ensure_safe_path(raw_path)
                meta_path = ensure_safe_path(meta_path)
                raw_path.write_bytes(body)
                metadata = {
                    "url": url,
                    "retrievedAtUTC": retrieved_at,
                    "rawSha256": hashlib.sha256(body).hexdigest(),
                }
                meta_path.write_text(
                    json.dumps(metadata, ensure_ascii=False, allow_nan=False, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                try:
                    payload = json.loads(
                        body.decode("utf-8", errors="strict"),
                        parse_constant=_reject_json_constant,
                    )
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                    _append_rejection(
                        output_dir,
                        seed,
                        "HTTP 200 study payload was not strict UTF-8 JSON",
                        status_code,
                    )
                    raise RuntimeError(
                        f"ClinicalTrials.gov payload for {seed.nct_id} is invalid"
                    ) from error
                if not isinstance(payload, dict):
                    raise ValueError("study API response must be a JSON object")
                return body, payload, retrieved_at, raw_path.relative_to(output_dir).as_posix()

            _append_jsonl(
                output_dir / "raw" / "requests.jsonl",
                {
                    "url": url,
                    "attempt": attempt + 1,
                    "retrievedAtUTC": retrieved_at,
                    "status": status_code,
                },
            )
            if attempt == 0 and status_code in _RETRYABLE_STATUS:
                time.sleep(0.25)
                continue
            _append_rejection(
                output_dir, seed, f"ClinicalTrials.gov returned HTTP {status_code}", status_code
            )
            raise RuntimeError(f"ClinicalTrials.gov returned HTTP {status_code} for {seed.nct_id}")
        except httpx.HTTPError as error:
            _append_jsonl(
                output_dir / "raw" / "requests.jsonl",
                {
                    "url": url,
                    "attempt": attempt + 1,
                    "retrievedAtUTC": retrieved_at,
                    "status": None,
                    "errorType": type(error).__name__,
                },
            )
            if attempt == 0:
                time.sleep(0.25)
                continue
            _append_rejection(
                output_dir, seed, f"ClinicalTrials.gov request failed: {type(error).__name__}"
            )
            raise RuntimeError(f"ClinicalTrials.gov request failed for {seed.nct_id}") from error
    raise RuntimeError(f"ClinicalTrials.gov did not return a record for {seed.nct_id}")


def _case_evidence(
    *,
    seed: TrialSeed,
    title: str,
    updated_date: str,
    retrieved_at: str,
    raw_path: str,
    raw_bytes: bytes,
    fact_excerpt: str,
    update_excerpt: str,
) -> list[dict[str, Any]]:
    digest = hashlib.sha256(raw_bytes).hexdigest()
    common = {
        "url": f"{PUBLIC_STUDY_URL}{seed.nct_id}",
        "title": f"ClinicalTrials.gov study record: {title}",
        "retrievedAtUTC": retrieved_at,
        "publishedAt": updated_date,
        "sourceRecordId": seed.nct_id,
        "upstreamRevision": (
            f"lastUpdatePostDate={updated_date}; Last Update Posted {updated_date}"
        ),
        "license": "unknown",
        "rawSha256": digest,
        "rawPath": raw_path,
    }
    return [
        {**common, "excerpt": fact_excerpt},
        {**common, "excerpt": update_excerpt},
    ]


def _case(
    seed: TrialSeed,
    *,
    question_type: str,
    prompt: str,
    answer: str,
    value: Any,
    version: str,
    evidence: list[dict[str, Any]],
    accepted_answers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "id": f"clinical-{seed.nct_id.casefold()}-{question_type}",
        "categoryId": CATEGORY_ID,
        "query": prompt,
        "temporal": {"kind": "version", "precision": "version", "version": version},
        "gold": {
            "answer": answer,
            "value": value,
            "acceptedAnswers": [answer, *(accepted_answers or [])],
        },
        "evidence": evidence,
        "derivation": {
            "sourceFamily": SOURCE_FAMILY,
            "generatorVersion": GENERATOR_VERSION,
            "questionType": question_type,
        },
    }


def _make_cases(
    seed: TrialSeed,
    body: bytes,
    payload: dict[str, Any],
    retrieved_at: str,
    raw_path: str,
) -> list[dict[str, Any]]:
    text = body.decode("utf-8", errors="strict")
    study, root = _record_sections(payload, seed.nct_id)
    protocol = study["protocolSection"]
    identity = protocol["identificationModule"]
    status = protocol["statusModule"]
    design = protocol["designModule"]
    outcomes = protocol["outcomesModule"]
    update_date, _update_precision = _update_date(status)
    if status.get("overallStatus") != seed.overall_status:
        raise ValueError(f"ClinicalTrials.gov status changed for selected record {seed.nct_id}")
    title = identity.get("briefTitle")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"ClinicalTrials.gov record {seed.nct_id} has no briefTitle")

    # The temporal version is deliberately the registry-visible update date.
    # Retrieval time remains provenance metadata, not an artificial instruction
    # that a search result could not contain.
    version = f"Last Update Posted {update_date}"
    update_excerpt = _path_excerpt(
        text, (*root, "protocolSection", "statusModule", "lastUpdatePostDateStruct")
    )
    outcome_path = (*root, "protocolSection", "outcomesModule", "primaryOutcomes")
    measure = _primary_measure(outcomes)
    outcome_excerpt = _outcome_excerpt(text, outcome_path, 0)
    outcome_case = _case(
        seed,
        question_type="primary_outcome_measure",
        prompt=(
            f"For ClinicalTrials.gov study {seed.nct_id} ({version}), what measure is listed "
            "for the first primary outcome? Give the registry's measure label only, not a "
            "study result."
        ),
        answer=measure,
        value=measure,
        version=version,
        evidence=_case_evidence(
            seed=seed,
            title=title,
            updated_date=update_date,
            retrieved_at=retrieved_at,
            raw_path=raw_path,
            raw_bytes=body,
            fact_excerpt=outcome_excerpt,
            update_excerpt=update_excerpt,
        ),
    )

    if seed.secondary_question == "registry_phase":
        phases = _phase_values(design)
        phase_answer = _phase_answer(phases)
        if phases == ["NA"]:
            raise ValueError(f"Selected phase case {seed.nct_id} has no applicable phase label")
        phase_case = _case(
            seed,
            question_type="registry_phase",
            prompt=(
                f"For ClinicalTrials.gov study {seed.nct_id} ({version}), which phase label or "
                "labels does the registry list? This is the registry phase field, not an FDA "
                "approval claim."
            ),
            answer=phase_answer,
            value=phases,
            version=version,
            accepted_answers=phases,
            evidence=_case_evidence(
                seed=seed,
                title=title,
                updated_date=update_date,
                retrieved_at=retrieved_at,
                raw_path=raw_path,
                raw_bytes=body,
                fact_excerpt=_path_excerpt(
                    text, (*root, "protocolSection", "designModule", "phases")
                ),
                update_excerpt=update_excerpt,
            ),
        )
        return [outcome_case, phase_case]

    completion_date, date_precision, completion_label = _completion(status)
    date_struct = status["completionDateStruct"]
    completion_answer = f"{completion_date} ({completion_label})"
    completion_case = _case(
        seed,
        question_type="overall_completion_date",
        prompt=(
            f"For ClinicalTrials.gov study {seed.nct_id} ({version}), what entry does the "
            "overall Study Completion Date field show, including its Actual/Estimated type?"
        ),
        answer=completion_answer,
        value={"date": completion_date, "type": date_struct["type"]},
        version=version,
        accepted_answers=[
            json.dumps(date_struct, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        ],
        evidence=_case_evidence(
            seed=seed,
            title=title,
            updated_date=update_date,
            retrieved_at=retrieved_at,
            raw_path=raw_path,
            raw_bytes=body,
            fact_excerpt=_path_excerpt(
                text, (*root, "protocolSection", "statusModule", "completionDateStruct")
            ),
            update_excerpt=update_excerpt,
        ),
    )
    # The date precision remains visible in the evidence and answer; no day is
    # invented for year/month-only values.
    if date_precision not in {"year", "month", "day"}:
        raise ValueError(f"Unsupported completion date precision for {seed.nct_id}")
    return [outcome_case, completion_case]


def _default_output_dir() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return (
        repository_root
        / "results"
        / "query-gold-curation"
        / "first-five-v1"
        / "categories"
        / CATEGORY_ID
    )


def _preflight_output_dir(output_dir: Path) -> Path:
    """Validate the category directory, raw caches, and request ledgers before I/O."""
    safe_output = ensure_safe_path(Path(output_dir))
    raw_dir = ensure_safe_path(safe_output / "raw")
    studies_dir = ensure_safe_path(raw_dir / "studies")
    for name in (
        "discovery-requests.jsonl",
        "precollection-probes.jsonl",
        "requests.jsonl",
        "rejected.jsonl",
    ):
        ensure_safe_path(raw_dir / name)
    ensure_safe_path(studies_dir)
    return safe_output


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Return reproducible query/gold records, preferring pinned raw caches."""
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 50:
        raise ValueError("count must be an integer between 0 and 50")
    if count == 0:
        return []
    output_dir = _preflight_output_dir(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = _preflight_output_dir(output_dir)
    records: list[dict[str, Any]] = []
    client: httpx.Client | None = None
    try:
        for seed in TRIALS[: (count + 1) // 2]:
            source = _cached_record_file(output_dir, seed)
            if source is None:
                if client is None:
                    client = httpx.Client(
                        timeout=httpx.Timeout(20.0, connect=5.0),
                        follow_redirects=False,
                        trust_env=False,
                        headers={"User-Agent": USER_AGENT},
                    )
                source = _fetch_record(output_dir, seed, client)
            try:
                cases = _make_cases(seed, *source)
            except (KeyError, TypeError, ValueError) as error:
                _append_rejection(output_dir, seed, f"source field validation failed: {error}")
                raise ValueError(
                    f"Rejected ClinicalTrials.gov record {seed.nct_id}: {error}"
                ) from error
            records.extend(cases)
        return records[:count]
    finally:
        if client is not None:
            client.close()


def _write_cases(output_dir: Path, cases: list[dict[str, Any]]) -> Path:
    output_dir = _preflight_output_dir(output_dir)
    target = output_dir / "cases.jsonl"
    target = ensure_safe_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target = ensure_safe_path(target)
    text = "".join(
        json.dumps(case, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for case in cases
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=target.parent,
        prefix=".cases.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(text)
        temporary_path = Path(temporary.name)
    ensure_safe_path(temporary_path)
    target = ensure_safe_path(target)
    temporary_path.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument("--count", type=int, default=50)
    arguments = parser.parse_args(argv)
    try:
        cases = collect(arguments.output_dir, arguments.count)
        target = _write_cases(arguments.output_dir, cases)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"clinical query-gold collection failed: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {len(cases)} clinical query-gold cases to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
