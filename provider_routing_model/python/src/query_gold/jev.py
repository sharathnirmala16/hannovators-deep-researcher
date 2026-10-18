"""Bounded CommandCode Jev evidence-consistency reviewer (live calls are opt-in)."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

import httpx
from pydantic import Field, JsonValue, ValidationError, field_validator

from query_gold.io import (
    atomic_write_json,
    ensure_safe_path,
    json_bytes,
    read_json,
    sha256_bytes,
)
from query_gold.models import QueryGoldCase, StrictModel
from query_gold.validation import CATEGORY_IDS

JEV_ENDPOINT = "https://api.commandcode.ai/provider/v1/systemone"
JEV_MODEL: Literal["typesafe/jev-1.14.0"] = "typesafe/jev-1.14.0"
JEV_TIMEOUT_SECONDS = 30.0
JEV_MAX_STATE_CHARS = 12_000
JEV_MAX_RETRIES = 1
JEV_SAMPLE_PER_CATEGORY = 3
JEV_MAX_PHYSICAL_REQUESTS = (2 + len(CATEGORY_IDS) * JEV_SAMPLE_PER_CATEGORY) * (
    1 + JEV_MAX_RETRIES
)
JEV_RUBRIC_VERSION = "query-gold-jev-rubric/v2"
JEV_CALIBRATION_VERSION = "query-gold-jev-calibration/v2"
EXPECTED_ANSWER_IDS = {
    "direct_search_answerable",
    "gold_supported",
    "temporal_coherent",
    "single_answer",
}
DEFAULT_THRESHOLDS = {
    "direct_search_answerable": 0.80,
    "gold_supported": 0.80,
    "temporal_coherent": 0.80,
    "single_answer": 0.80,
}
API_KEY_ENV_NAMES = ("CMD_API_KEY", "COMMANDCODE_API_KEY", "COMMANDCODE_KEY")
ZERO_RETENTION_ENV_NAMES = (
    "CMD_ZDR",
    "COMMANDCODE_ZERO_DATA_RETENTION",
    "CMD_ZERO_DATA_RETENTION",
)

QuestionId = Literal[
    "direct_search_answerable",
    "gold_supported",
    "temporal_coherent",
    "single_answer",
]


class JevQuestion(StrictModel):
    type: Literal["noul"]
    instructions: Annotated[str, Field(min_length=1, max_length=1200)]


class JevRequest(StrictModel):
    model: Literal["typesafe/jev-1.14.0"]
    state: Annotated[str, Field(min_length=1, max_length=JEV_MAX_STATE_CHARS)]
    questions: dict[QuestionId, JevQuestion]

    @field_validator("questions")
    @classmethod
    def exactly_one_of_each_question(
        cls, value: dict[QuestionId, JevQuestion]
    ) -> dict[QuestionId, JevQuestion]:
        if set(value) != EXPECTED_ANSWER_IDS:
            raise ValueError("request must ask each rubric question exactly once")
        return value


class JevAnswer(StrictModel):
    type: Literal["noul"]
    noul: int | float = Field(ge=0, le=1)

    @field_validator("noul")
    @classmethod
    def finite_probability(cls, value: int | float) -> int | float:
        if isinstance(value, bool) or not math.isfinite(float(value)):
            raise ValueError("noul must be a finite probability")
        return value


class JevResponse(StrictModel):
    model: Literal["typesafe/jev", "typesafe/jev-1.14.0"]
    answers: dict[str, JevAnswer]
    usage: dict[str, JsonValue]


@dataclass(frozen=True)
class JevConfig:
    thresholds: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    timeout_seconds: float = JEV_TIMEOUT_SECONDS
    max_state_chars: int = JEV_MAX_STATE_CHARS
    max_physical_requests: int = JEV_MAX_PHYSICAL_REQUESTS
    max_retries: int = JEV_MAX_RETRIES
    sample_per_category: int = JEV_SAMPLE_PER_CATEGORY
    seed: int = 20261017

    def __post_init__(self) -> None:
        if set(self.thresholds) != EXPECTED_ANSWER_IDS:
            raise ValueError("Jev thresholds must define every rubric question")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
            for value in self.thresholds.values()
        ):
            raise ValueError("Jev thresholds must be finite probabilities")
        if not 0 < self.timeout_seconds <= JEV_TIMEOUT_SECONDS:
            raise ValueError("Jev timeout cannot exceed 30 seconds")
        if not 0 < self.max_state_chars <= JEV_MAX_STATE_CHARS:
            raise ValueError("Jev state cap cannot exceed 12,000 characters")
        if not 0 <= self.max_retries <= JEV_MAX_RETRIES:
            raise ValueError("Jev allows at most one retry")
        if not 0 < self.max_physical_requests <= JEV_MAX_PHYSICAL_REQUESTS:
            raise ValueError(
                f"Jev request cap cannot exceed {JEV_MAX_PHYSICAL_REQUESTS} physical requests"
            )
        if not 0 < self.sample_per_category <= JEV_SAMPLE_PER_CATEGORY:
            raise ValueError("Jev samples at most three cases per category")


class ResponseLike(Protocol):
    status_code: int

    def json(self) -> Any: ...


class JevTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> ResponseLike: ...


class JevRequestClient(Protocol):
    def post(self, request: JevRequest, *, timeout: float) -> ResponseLike: ...

    def close(self) -> None: ...


class HttpxJevTransport:
    """Small stateful HTTP adapter; callers own closing it."""

    def __init__(self) -> None:
        self._client = httpx.Client(follow_redirects=False)

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> httpx.Response:
        return self._client.post(url, headers=headers, json=json, timeout=timeout)

    def close(self) -> None:
        self._client.close()


class CommandCodeJevClient:
    """Authenticated Jev API adapter that never exposes headers to the report."""

    def __init__(self, api_key: str, transport: JevTransport | None = None) -> None:
        if not api_key.strip():
            raise ValueError("CommandCode API key is required")
        self._api_key = api_key
        self._transport = transport or HttpxJevTransport()

    def post(self, request: JevRequest, *, timeout: float) -> ResponseLike:
        return self._transport.post(
            JEV_ENDPOINT,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=request.model_dump(mode="json", exclude_none=True),
            timeout=timeout,
        )

    def close(self) -> None:
        close = getattr(self._transport, "close", None)
        if callable(close):
            close()


@dataclass(frozen=True)
class ReviewCandidate:
    case_id: str
    category_id: str
    case_sha256: str
    state: dict[str, Any]
    calibration_expected: str | None = None


RUBRIC_QUESTIONS: dict[QuestionId, dict[str, str]] = {
    "direct_search_answerable": {
        "type": "noul",
        "instructions": (
            "Using only the supplied state, could a single direct search for this query surface a "
            "normal public HTML/PDF/versioned-doc page stating the gold answer with matching scope "
            "and units? This is not a top-five guarantee; do not use outside knowledge. Return a "
            "yes probability."
        ),
    },
    "gold_supported": {
        "type": "noul",
        "instructions": (
            "Does the supplied excerpt directly support the gold answer? Use only the evidence; "
            "do not use outside knowledge or infer missing facts. Return a yes probability."
        ),
    },
    "temporal_coherent": {
        "type": "noul",
        "instructions": (
            "Do query scope and evidence dates/version cohere with the gold answer? Missing or "
            "conflicting scope is not established. Return a yes probability."
        ),
    },
    "single_answer": {
        "type": "noul",
        "instructions": (
            "According only to query and evidence, is the gold answer defensible and single rather "
            "than one of multiple materially different answers? Return a yes probability."
        ),
    },
}


def api_key_from_environment(environ: Mapping[str, str] | None = None) -> str | None:
    """Return a configured key without logging, printing, or loading dotenv files."""
    values = os.environ if environ is None else environ
    for name in API_KEY_ENV_NAMES:
        value = values.get(name)
        if value and value.strip():
            return value
    return None


def zero_data_retention_requested(environ: Mapping[str, str] | None = None) -> bool:
    """Detect an explicit ZDR requirement; Jev has no configured ZDR mode."""
    values = os.environ if environ is None else environ
    truthy = {"1", "true", "yes", "on"}
    return any(
        (values.get(name) or "").strip().casefold() in truthy for name in ZERO_RETENTION_ENV_NAMES
    )


def _candidate_from_case(case: QueryGoldCase) -> ReviewCandidate:
    state = {
        "query": case.query,
        "temporal": case.temporal.model_dump(mode="json", exclude_none=True),
        "gold": case.gold.model_dump(mode="json", exclude_none=True),
        "evidence": [
            {
                "url": evidence.url,
                "title": evidence.title,
                "publishedAt": evidence.publishedAt,
                "effectiveDate": evidence.effectiveDate,
                "upstreamRevision": evidence.upstreamRevision,
                "excerpt": evidence.excerpt,
            }
            for evidence in case.evidence
        ],
    }
    case_hash = sha256_bytes(json_bytes(case))
    return ReviewCandidate(case.id, case.categoryId, case_hash, state)


def _calibration_candidates(
    cases: list[QueryGoldCase],
) -> tuple[ReviewCandidate, ReviewCandidate]:
    """Build paired real-evidence controls from the first sorted numeric finance case."""
    numeric_finance = sorted(
        (
            case
            for case in cases
            if case.categoryId == "01_earnings_corporate_finance"
            and isinstance(case.gold.value, (int, float))
            and not isinstance(case.gold.value, bool)
        ),
        key=lambda case: case.id,
    )
    if not numeric_finance:
        raise ValueError("Jev calibration requires a numeric finance case with source evidence")

    source_candidate = _candidate_from_case(numeric_finance[0])
    positive = ReviewCandidate(
        case_id="calibration-positive",
        category_id=source_candidate.category_id,
        case_sha256=sha256_bytes(
            json_bytes(
                {
                    "calibrationVersion": JEV_CALIBRATION_VERSION,
                    "role": "positive",
                    "sourceCaseSha256": source_candidate.case_sha256,
                }
            )
        ),
        state=source_candidate.state,
        calibration_expected="positive",
    )
    negative_state = copy.deepcopy(source_candidate.state)
    negative_gold = negative_state["gold"]
    source_text = " ".join(evidence["excerpt"] for evidence in negative_state["evidence"])
    source_digits = re.sub(r"\D", "", source_text)
    counterfactual_value = 987_654_321_012_345
    while str(counterfactual_value) in source_digits:
        counterfactual_value += 1
    negative_gold["answer"] = str(counterfactual_value)
    negative_gold["value"] = counterfactual_value
    negative_gold["acceptedAnswers"] = []
    negative = ReviewCandidate(
        case_id="calibration-negative",
        category_id=source_candidate.category_id,
        case_sha256=sha256_bytes(
            json_bytes(
                {
                    "calibrationVersion": JEV_CALIBRATION_VERSION,
                    "role": "negative",
                    "sourceCaseSha256": source_candidate.case_sha256,
                    "state": negative_state,
                }
            )
        ),
        state=negative_state,
        calibration_expected="negative",
    )
    return positive, negative


def stratified_sample(
    cases: list[QueryGoldCase], *, seed: int, per_category: int = JEV_SAMPLE_PER_CATEGORY
) -> list[QueryGoldCase]:
    """Deterministically round-robin question subtypes within each category."""
    if not 0 < per_category <= JEV_SAMPLE_PER_CATEGORY:
        raise ValueError("Sampler takes at most three records per category")
    selected: list[QueryGoldCase] = []
    for category in CATEGORY_IDS:
        groups: dict[str, list[QueryGoldCase]] = {}
        for case in cases:
            if case.categoryId == category:
                groups.setdefault(case.derivation.questionType, []).append(case)
        seed_bytes = hashlib.sha256(f"{seed}:{category}".encode()).digest()
        rng = random.Random(int.from_bytes(seed_bytes[:8], "big"))
        question_types = sorted(groups)
        rng.shuffle(question_types)
        for group in groups.values():
            group.sort(key=lambda case: case.id)
            rng.shuffle(group)
        category_sample: list[QueryGoldCase] = []
        while len(category_sample) < per_category:
            progressed = False
            for question_type in question_types:
                bucket = groups[question_type]
                if bucket:
                    category_sample.append(bucket.pop())
                    progressed = True
                    if len(category_sample) == per_category:
                        break
            if not progressed:
                raise ValueError(
                    f"Category {category} has fewer than {per_category} cases to sample"
                )
        selected.extend(category_sample)
    return selected


def _validate_usage(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Keep native scalar usage while rejecting payload text or credential-shaped fields."""
    sensitive_key = re.compile(
        r"(?:api.?key|authorization|password|secret|prompt|answer|content|message|headers?|"
        r"(?:^|_)body(?:_|$)|error|response|request(?!_id))",
        re.IGNORECASE,
    )

    token_count_keys = {
        "completion_tokens",
        "input_tokens",
        "output_tokens",
        "prompt_tokens",
        "total_tokens",
        "cached_tokens",
        "reasoning_tokens",
    }

    def visit(node: JsonValue, parent_key: str = "") -> None:
        numeric_token_count = (
            parent_key.casefold() in token_count_keys
            and isinstance(node, (int, float))
            and not isinstance(node, bool)
        )
        if sensitive_key.search(parent_key) and not numeric_token_count:
            raise ValueError("usage contains an unsafe field")
        if isinstance(node, float) and not math.isfinite(node):
            raise ValueError("usage contains a non-finite number")
        if isinstance(node, str) and (len(node) > 128 or "\n" in node or "\r" in node):
            raise ValueError("usage contains an unsafe string")
        if isinstance(node, dict):
            for key, item in node.items():
                if not isinstance(key, str) or len(key) > 80:
                    raise ValueError("usage contains an invalid field name")
                visit(item, key)
        elif isinstance(node, list):
            if len(node) > 100:
                raise ValueError("usage list is too large")
            for item in node:
                visit(item, parent_key)

    visit(value)
    return value


def _reported_usd(usage: dict[str, JsonValue]) -> float | None:
    accepted = {"reported_usd", "reportedusd", "cost_usd", "costusd", "usd_cost", "price_usd"}

    def find(node: JsonValue) -> float | None:
        if isinstance(node, dict):
            for key, value in node.items():
                if (
                    key.casefold() in accepted
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                ):
                    amount = float(value)
                    if math.isfinite(amount) and amount >= 0:
                        return amount
                found = find(value)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = find(value)
                if found is not None:
                    return found
        return None

    return find(usage)


def _safe_error_code(error: Exception) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.TransportError):
        return "transport_error"
    if isinstance(error, (ValidationError, ValueError, TypeError, KeyError)):
        return "invalid_response"
    return "request_error"


def _case_cache_key(case_sha256: str, rubric_sha256: str) -> str:
    material = f"{case_sha256}\n{JEV_MODEL}\n{rubric_sha256}".encode()
    return hashlib.sha256(material).hexdigest()


def _serialize_state(state: Mapping[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _state_char_count(state: Mapping[str, Any] | str) -> int:
    serialized = state if isinstance(state, str) else _serialize_state(state)
    return len(serialized)


def _file_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _probabilities(response: JevResponse) -> dict[str, float]:
    if set(response.answers) != EXPECTED_ANSWER_IDS:
        raise ValueError("response must provide all and only the rubric answer IDs")
    return {question_id: float(answer.noul) for question_id, answer in response.answers.items()}


def _calibration_probability(result: dict[str, Any], question_id: str, default: float) -> float:
    probabilities = result.get("probabilities")
    if not isinstance(probabilities, dict):
        return default
    value = probabilities.get(question_id, default)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


class JevReviewer:
    """One bounded run with local, incremental persistence and decision caching."""

    def __init__(
        self,
        client: JevRequestClient | None,
        artifact_root: Path,
        *,
        config: JevConfig | None = None,
    ) -> None:
        self._client = client
        self._root = artifact_root
        self._config = config or JevConfig()
        rubric = {
            "version": JEV_RUBRIC_VERSION,
            "calibrationVersion": JEV_CALIBRATION_VERSION,
            "model": JEV_MODEL,
            "questions": RUBRIC_QUESTIONS,
            "thresholds": dict(sorted(self._config.thresholds.items())),
        }
        self._rubric_sha256 = sha256_bytes(json_bytes(rubric))
        self._cache_path = artifact_root / "jev-cache.json"
        self._report_path = artifact_root / "jev-reports" / f"jev-review-{_file_timestamp()}.json"
        self._cache = self._load_cache()
        self._physical_requests = 0
        self._cache_hits = 0
        self._attempts: list[dict[str, Any]] = []
        self._report: dict[str, Any] = {
            "reportVersion": "query-gold-jev-review/v1",
            "status": "running",
            "startedAtUTC": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "model": JEV_MODEL,
            "endpoint": JEV_ENDPOINT,
            "rubricVersion": JEV_RUBRIC_VERSION,
            "calibrationVersion": JEV_CALIBRATION_VERSION,
            "rubricSha256": self._rubric_sha256,
            "thresholds": dict(self._config.thresholds),
            "limits": {
                "timeoutSeconds": self._config.timeout_seconds,
                "maxStateChars": self._config.max_state_chars,
                "maxRetries": self._config.max_retries,
                "maxPhysicalRequests": self._config.max_physical_requests,
                "samplePerCategory": self._config.sample_per_category,
                "maxLogicalRequests": 2 + len(CATEGORY_IDS) * self._config.sample_per_category,
            },
            "physicalRequests": 0,
            "cacheHits": 0,
            "attempts": self._attempts,
            "calibration": {
                "version": JEV_CALIBRATION_VERSION,
                "passed": None,
                "results": [],
            },
            "results": [],
            "datasetDecision": "not_automatically_reviewed",
            "cost": {"reportedUsdTotal": None, "estimatedUsd": None},
        }
        ensure_safe_path(self._root)

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        try:
            payload = read_json(self._cache_path)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            raise ValueError(
                "Jev decision cache is unsafe or invalid; refusing to make uncached calls"
            ) from None
        if (
            not isinstance(payload, dict)
            or payload.get("cacheVersion") != "query-gold-jev-cache/v1"
        ):
            raise ValueError("Jev decision cache has an unsupported format")
        decisions = payload.get("decisions")
        if not isinstance(decisions, dict):
            raise ValueError("Jev decision cache has an invalid decisions map")
        return decisions

    def _persist_report(self) -> None:
        self._report["physicalRequests"] = self._physical_requests
        self._report["cacheHits"] = self._cache_hits
        atomic_write_json(self._report_path, self._report)

    def _persist_cache(self) -> None:
        atomic_write_json(
            self._cache_path,
            {
                "cacheVersion": "query-gold-jev-cache/v1",
                "model": JEV_MODEL,
                "rubricSha256": self._rubric_sha256,
                "decisions": self._cache,
            },
        )

    def _decision(self, probabilities: Mapping[str, float]) -> str:
        return (
            "pass"
            if all(
                probabilities.get(key, -1.0) >= self._config.thresholds[key]
                for key in EXPECTED_ANSWER_IDS
            )
            else "review_required"
        )

    def _make_request(self, state: dict[str, Any]) -> JevRequest:
        questions = {
            question_id: JevQuestion.model_validate(item, strict=True)
            for question_id, item in RUBRIC_QUESTIONS.items()
        }
        return JevRequest(
            model=JEV_MODEL,
            state=_serialize_state(state),
            questions=questions,
        )

    def _read_cached(self, candidate: ReviewCandidate, cache_key: str) -> dict[str, Any] | None:
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        if (
            not isinstance(entry, dict)
            or entry.get("caseSha256") != candidate.case_sha256
            or entry.get("model") != JEV_MODEL
            or entry.get("rubricSha256") != self._rubric_sha256
            or not isinstance(entry.get("probabilities"), dict)
        ):
            raise ValueError("Jev decision cache entry does not match its cache key")
        probabilities = entry["probabilities"]
        if set(probabilities) != EXPECTED_ANSWER_IDS or any(
            not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not 0 <= value <= 1
            for value in probabilities.values()
        ):
            raise ValueError("Jev decision cache has invalid probabilities")
        result = dict(entry)
        result["decision"] = self._decision(probabilities)
        result["cached"] = True
        self._cache_hits += 1
        return result

    def _request_once(
        self,
        candidate: ReviewCandidate,
        cache_key: str,
        attempt_number: int,
    ) -> dict[str, Any] | None:
        if self._physical_requests >= self._config.max_physical_requests:
            return None
        if self._client is None:
            raise ValueError("A live Jev client is required unless ZDR is requested")
        request = self._make_request(candidate.state)
        request_chars = _state_char_count(request.state)
        if request_chars > self._config.max_state_chars:
            return {
                "status": "review_required",
                "reasonCode": "state_too_large",
                "caseId": candidate.case_id,
                "categoryId": candidate.category_id,
                "caseSha256": candidate.case_sha256,
                "cacheKey": cache_key,
                "stateChars": request_chars,
                "probabilities": {},
                "usage": None,
                "reportedUsd": None,
                "estimatedUsd": None,
                "cached": False,
                "attemptCount": 0,
            }

        self._physical_requests += 1
        started_at = datetime.now(UTC)
        attempt: dict[str, Any] = {
            "caseId": candidate.case_id,
            "caseSha256": candidate.case_sha256,
            "cacheKey": cache_key,
            "attempt": attempt_number,
            "startedAtUTC": started_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "timeoutSeconds": self._config.timeout_seconds,
            "stateChars": request_chars,
        }
        try:
            response = self._client.post(request, timeout=self._config.timeout_seconds)
            status_code = int(response.status_code)
            attempt["httpStatus"] = status_code
            if status_code < 200 or status_code >= 300:
                attempt["status"] = "http_error"
                attempt["errorCode"] = "provider_http_error"
                result = None
            else:
                raw = response.json()
                parsed = JevResponse.model_validate(raw, strict=True)
                probabilities = _probabilities(parsed)
                usage = _validate_usage(parsed.usage)
                attempt["status"] = "success"
                attempt["usage"] = usage
                attempt["probabilities"] = probabilities
                attempt["reportedUsd"] = _reported_usd(usage)
                result = {
                    "caseId": candidate.case_id,
                    "categoryId": candidate.category_id,
                    "caseSha256": candidate.case_sha256,
                    "cacheKey": cache_key,
                    "status": "valid_response",
                    "decision": self._decision(probabilities),
                    "reasonCode": None,
                    "probabilities": probabilities,
                    "usage": usage,
                    "reportedUsd": _reported_usd(usage),
                    "estimatedUsd": None,
                    "cached": False,
                    "attemptCount": attempt_number,
                }
        except Exception as error:
            attempt["status"] = _safe_error_code(error)
            attempt["errorCode"] = _safe_error_code(error)
            error_response = getattr(error, "response", None)
            response_status = getattr(error_response, "status_code", None)
            if isinstance(response_status, int):
                attempt["httpStatus"] = response_status
            result = None

        ended_at = datetime.now(UTC)
        attempt["completedAtUTC"] = ended_at.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
        attempt["durationMs"] = max(0, int((ended_at - started_at).total_seconds() * 1000))
        self._attempts.append(attempt)
        self._persist_report()

        if result is not None:
            entry = {
                "caseSha256": candidate.case_sha256,
                "model": JEV_MODEL,
                "rubricSha256": self._rubric_sha256,
                "decision": result["decision"],
                "probabilities": result["probabilities"],
                "usage": result["usage"],
                "reportedUsd": result["reportedUsd"],
                "attemptCount": attempt_number,
                "completedAtUTC": attempt["completedAtUTC"],
            }
            self._cache[cache_key] = entry
            self._persist_cache()
            return result
        return None

    def _review_candidate(self, candidate: ReviewCandidate) -> dict[str, Any]:
        cache_key = _case_cache_key(candidate.case_sha256, self._rubric_sha256)
        cached = self._read_cached(candidate, cache_key)
        if cached is not None:
            cached.update(
                {
                    "caseId": candidate.case_id,
                    "categoryId": candidate.category_id,
                    "status": "valid_response",
                    "reasonCode": None,
                    "attemptCount": cached.get("attemptCount", 0),
                }
            )
            return cached

        state_chars = _state_char_count(candidate.state)
        if state_chars > self._config.max_state_chars:
            return {
                "caseId": candidate.case_id,
                "categoryId": candidate.category_id,
                "caseSha256": candidate.case_sha256,
                "cacheKey": cache_key,
                "status": "review_required",
                "reasonCode": "state_too_large",
                "stateChars": state_chars,
                "probabilities": {},
                "usage": None,
                "reportedUsd": None,
                "estimatedUsd": None,
                "cached": False,
                "attemptCount": 0,
            }

        last_error_code = "physical_request_limit_reached"
        attempts_before = len(self._attempts)
        for attempt_number in range(1, self._config.max_retries + 2):
            if self._physical_requests >= self._config.max_physical_requests:
                break
            result = self._request_once(candidate, cache_key, attempt_number)
            if result is not None:
                return result
            if self._attempts:
                last_error_code = str(self._attempts[-1].get("errorCode", "provider_failure"))

        return {
            "caseId": candidate.case_id,
            "categoryId": candidate.category_id,
            "caseSha256": candidate.case_sha256,
            "cacheKey": cache_key,
            "status": "review_required",
            "reasonCode": last_error_code,
            "probabilities": {},
            "usage": None,
            "reportedUsd": None,
            "estimatedUsd": None,
            "cached": False,
            "attemptCount": len(self._attempts) - attempts_before,
        }

    def _calibration_passed(self, results: list[dict[str, Any]]) -> bool:
        if len(results) != 2 or any(result.get("status") != "valid_response" for result in results):
            return False
        by_id = {result["caseId"]: result for result in results}
        positive = by_id.get("calibration-positive")
        negative = by_id.get("calibration-negative")
        if positive is None or negative is None:
            return False
        positive_ok = all(
            _calibration_probability(positive, question_id, 0.0)
            >= self._config.thresholds[question_id]
            for question_id in EXPECTED_ANSWER_IDS
        )
        negative_ok = _calibration_probability(negative, "gold_supported", 1.0) <= (
            1.0 - self._config.thresholds["gold_supported"]
        )
        return positive_ok and negative_ok

    def _apply_calibration(
        self, result: dict[str, Any], calibration_passed: bool
    ) -> dict[str, Any]:
        if result.get("status") != "valid_response":
            result["status"] = "review_required"
            return result
        if not calibration_passed:
            result["status"] = "review_required"
            result["reasonCode"] = "calibration_failed"
        else:
            result["status"] = result.get("decision", "review_required")
            result["reasonCode"] = None if result["status"] == "pass" else "below_threshold"
        return result

    def _update_cost_summary(self) -> None:
        successful = [attempt for attempt in self._attempts if attempt.get("status") == "success"]
        reported: list[float] = []
        for attempt in successful:
            value = attempt.get("reportedUsd")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                reported.append(float(value))
        if successful and len(reported) == len(successful):
            self._report["cost"]["reportedUsdTotal"] = sum(reported)
        else:
            self._report["cost"]["reportedUsdTotal"] = None
        self._report["cost"]["estimatedUsd"] = None

    def run(
        self,
        cases: list[QueryGoldCase],
        *,
        zero_data_retention_requested: bool = False,
    ) -> dict[str, Any]:
        """Review two calibrations plus at most three stratified cases/category."""
        sampled = stratified_sample(
            cases,
            seed=self._config.seed,
            per_category=self._config.sample_per_category,
        )
        self._report["sampler"] = {
            "seed": self._config.seed,
            "samplePerCategory": self._config.sample_per_category,
            "selectedCaseIds": [case.id for case in sampled],
            "selectedCount": len(sampled),
            "calibrationCount": 2,
            "logicalRequestUpperBound": len(sampled) + 2,
        }
        self._persist_report()

        if zero_data_retention_requested:
            self._report["status"] = "unsupported_zdr_requested"
            self._report["reasonCode"] = "jev_zero_data_retention_unsupported"
            self._report["completedAtUTC"] = (
                datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
            )
            self._persist_report()
            return self._report
        if self._client is None:
            raise ValueError("A live Jev client is required unless ZDR is requested")

        calibration_candidates = _calibration_candidates(cases)
        calibration_results: list[dict[str, Any]] = []
        for candidate in calibration_candidates:
            result = self._review_candidate(candidate)
            result["expectedCalibration"] = candidate.calibration_expected
            calibration_results.append(result)
            self._report["calibration"]["results"] = calibration_results
            self._report["calibration"]["passed"] = self._calibration_passed(calibration_results)
            self._persist_report()

        calibration_passed = self._calibration_passed(calibration_results)
        self._report["calibration"]["passed"] = calibration_passed
        for case in sampled:
            result = self._review_candidate(_candidate_from_case(case))
            self._report["results"].append(self._apply_calibration(result, calibration_passed))
            self._persist_report()

        self._update_cost_summary()
        self._report["status"] = "completed"
        self._report["reviewCoverage"] = {
            "datasetCaseCount": len(cases),
            "sampledCaseCount": len(sampled),
            "sampledFraction": len(sampled) / len(cases) if cases else 0.0,
            "unsampledCaseCount": len(cases) - len(sampled),
            "allCasesAutomaticallyReviewed": False,
        }
        self._report["completedAtUTC"] = (
            datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        )
        self._persist_report()
        return self._report

    @property
    def report_path(self) -> Path:
        return self._report_path


def run_jev_review(
    cases: list[QueryGoldCase],
    artifact_root: Path,
    *,
    api_key: str | None,
    config: JevConfig | None = None,
    transport: JevTransport | None = None,
    zdr_requested: bool = False,
) -> tuple[dict[str, Any], Path]:
    """Opt-in entry point; no key means no client and no outbound request."""
    active_config = config or JevConfig()
    if zdr_requested:
        reviewer = JevReviewer(
            None,
            artifact_root,
            config=active_config,
        )
        report = reviewer.run(cases, zero_data_retention_requested=True)
        return report, reviewer.report_path
    if not api_key:
        raise ValueError(
            "Set CMD_API_KEY, COMMANDCODE_API_KEY, or COMMANDCODE_KEY before live Jev review"
        )
    client = CommandCodeJevClient(api_key, transport=transport)
    reviewer = JevReviewer(client, artifact_root, config=active_config)
    try:
        report = reviewer.run(cases)
    finally:
        client.close()
    return report, reviewer.report_path
