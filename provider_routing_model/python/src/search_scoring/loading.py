"""Join collected search runs with explicitly supplied private answers, offline only.

Every (query, provider) pair is classified from the provider's latest terminal record:
  success  - results returned; quality = relevance score R in [0, 1]
  failure  - provider-side error or zero results; quality = 0 (penalized)
  missing  - not attributable to search quality (billing 402, harness request budget,
             cancellation, or no record); excluded from aggregates and reported as coverage
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from query_gold.io import read_json, read_jsonl
from query_gold.models import PrivateBenchmarkAnswer
from search_scoring.categories import category_for
from search_scoring.relevance import (
    Relevance,
    RelevanceWeights,
    answer_profile,
    score_response,
)
from search_urls.models import CaseResultRecord
from search_urls.persistence import load_benchmark

Outcome = Literal["success", "failure", "missing"]
_MISSING_ERROR_CODES = frozenset({"request_limit"})
_MISSING_STATUS_CODES = frozenset({402})


@dataclass(frozen=True, slots=True)
class Questions:
    sha256: str
    prompts: dict[str, str]


@dataclass(frozen=True, slots=True)
class RunSource:
    provider: str
    directory: Path
    config_sha256: str
    dataset_sha256: str


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    provider: str
    case_id: str
    category: str
    outcome: Outcome
    reason: str | None
    quality: float | None
    relevance: Relevance | None
    answer_informative: bool
    result_count: int
    attempts: int
    latency_ms: float | None
    cost_usd: float | None


def load_questions(path: Path) -> Questions:
    _, cases, sha256 = load_benchmark(path)
    return Questions(sha256, {case.case_id: case.query for case in cases})


def load_answers(path: Path, questions: Questions) -> dict[str, PrivateBenchmarkAnswer]:
    """Load the explicitly selected private answer file and require an exact ID/prompt join."""
    try:
        answers = [PrivateBenchmarkAnswer.model_validate(row) for row in read_jsonl(path)]
    except ValidationError:
        raise ValueError("private answers file has an invalid row") from None
    by_id = {answer.id: answer for answer in answers}
    if len(by_id) != len(answers) or by_id.keys() != questions.prompts.keys():
        raise ValueError("answer IDs must match the public benchmark IDs exactly")
    if any(by_id[case_id].prompt != prompt for case_id, prompt in questions.prompts.items()):
        raise ValueError("answer prompts must match the public benchmark prompts exactly")
    return by_id


def _source(provider: str, directory: Path) -> RunSource:
    manifest = read_json(directory / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("config", {}).get("provider") != provider:
        raise ValueError(f"run directory is not a {provider} collection: {directory.name}")
    return RunSource(
        provider, directory, str(manifest["configSHA256"]), str(manifest["datasetSHA256"])
    )


def discover_run(results_root: Path, provider: str, dataset_sha256: str) -> RunSource:
    """Pick the provider collection for this dataset with the most recorded cases."""
    candidates: list[tuple[int, RunSource]] = []
    for directory in sorted((results_root / provider).glob("*/")):
        if not (directory / "manifest.json").is_file():
            continue
        source = _source(provider, directory)
        if source.dataset_sha256 != dataset_sha256:
            continue
        results = directory / "results.jsonl"
        rows = read_jsonl(results) if results.is_file() else []
        candidates.append((len({row.get("caseId") for row in rows}), source))
    if not candidates:
        raise ValueError(f"no {provider} collection found for dataset {dataset_sha256[:12]}")
    return max(candidates, key=lambda item: item[0])[1]


def explicit_run(provider: str, directory: Path, dataset_sha256: str) -> RunSource:
    source = _source(provider, directory)
    if source.dataset_sha256 != dataset_sha256:
        raise ValueError(f"{provider} run was collected for a different dataset")
    return source


def _latest_records(directory: Path) -> dict[str, CaseResultRecord]:
    latest: dict[str, CaseResultRecord] = {}
    for row in read_jsonl(directory / "results.jsonl"):
        record = CaseResultRecord.model_validate(row)
        if record.repetition == 0:
            latest[record.case_id] = record
    return latest


def _finished_attempts(directory: Path) -> dict[str, Mapping[str, object]]:
    path = directory / "attempts.jsonl"
    rows = read_jsonl(path) if path.is_file() else []
    return {
        str(row["attemptId"]): row
        for row in rows
        if row.get("event") == "finished" and "attemptId" in row
    }


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _classify(record: CaseResultRecord | None) -> tuple[Outcome, str | None]:
    if record is None:
        return "missing", "no_record"
    if record.status == "cancelled":
        return "missing", "cancelled"
    if record.status == "error":
        error = record.error
        assert error is not None
        if error.code in _MISSING_ERROR_CODES:
            return "missing", error.code
        if error.status_code in _MISSING_STATUS_CODES:
            return "missing", f"billing_{error.status_code}"
        if error.code == "http_error" and error.status_code is not None:
            return "failure", f"http_{error.status_code}"
        return "failure", error.code
    assert record.response is not None
    if not record.response.results:
        return "failure", "zero_results"
    return "success", None


def load_outcomes(
    source: RunSource,
    questions: Questions,
    answers: Mapping[str, PrivateBenchmarkAnswer],
    *,
    k: int,
    weights: RelevanceWeights,
) -> list[QueryOutcome]:
    """Score every benchmark case for one provider, including cases it never answered."""
    records = _latest_records(source.directory)
    attempts = _finished_attempts(source.directory)
    outcomes: list[QueryOutcome] = []
    for case_id, prompt in questions.prompts.items():
        record = records.get(case_id)
        if record is not None and record.query != prompt:
            raise ValueError(f"{source.provider} record query differs from benchmark: {case_id}")
        outcome, reason = _classify(record)
        relevance: Relevance | None = None
        quality: float | None = None if outcome == "missing" else 0.0
        result_count = 0
        cost: float | None = None
        if record is not None and record.response is not None:
            result_count = len(record.response.results)
            total = record.response.cost.total_usd
            cost = float(total) if total is not None else None
            if outcome == "success":
                answer = answers[case_id]
                relevance = score_response(
                    record.response.results, answer.answer, answer.goldUrls, k=k, weights=weights
                )
                quality = relevance.score
        attempt_rows = [
            attempts[i] for i in (record.attempt_ids if record else []) if i in attempts
        ]
        latencies = [_number(row.get("latencyMs")) for row in attempt_rows]
        known_latencies = [value for value in latencies if value is not None]
        if cost is None and outcome == "failure":
            known_costs = [
                value
                for row in attempt_rows
                if (value := _number(row.get("reportedUsd") or row.get("estimatedUsd"))) is not None
            ]
            cost = sum(known_costs) if known_costs else None
        outcomes.append(
            QueryOutcome(
                provider=source.provider,
                case_id=case_id,
                category=category_for(case_id),
                outcome=outcome,
                reason=reason,
                quality=quality,
                relevance=relevance,
                answer_informative=answer_profile(answers[case_id].answer).informative,
                result_count=result_count,
                attempts=len(record.attempt_ids) if record else 0,
                latency_ms=sum(known_latencies) if known_latencies else None,
                cost_usd=cost,
            )
        )
    return outcomes
