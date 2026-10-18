"""Strict inputs, normalized results, and provider cost evidence."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

ProviderName = Literal[
    "brave",
    "exa",
    "firecrawl",
    "keenable",
    "parallel",
    "tavily",
    "tinyfish",
    "you",
]
NonEmpty = Annotated[str, StringConstraints(min_length=1)]
CaseId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]
_SENSITIVE_KEYS = frozenset(
    {
        "apikey",
        "authorization",
        "credential",
        "credentials",
        "key",
        "password",
        "secret",
        "signature",
        "token",
        "accesskey",
        "accesstoken",
    }
)
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def _decimal_from_json(value: object) -> Decimal | None:
    """Parse exact JSON decimal text without accepting binary floats or booleans."""
    if value is None or isinstance(value, Decimal):
        return value
    if isinstance(value, (bool, float)):
        raise TypeError("money must be an integer, decimal string, or Decimal")
    if isinstance(value, (str, int)):
        try:
            return Decimal(value)
        except InvalidOperation:
            raise ValueError("money must be a valid decimal") from None
    raise TypeError("money must be an integer, decimal string, or Decimal")


class StrictModel(BaseModel):
    """Base for JSON-facing models with camelCase aliases and no unknown fields."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_default=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )


def _safe_url(value: str) -> str:
    """Validate a public HTTP URL without changing provider evidence."""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("url must not contain embedded credentials")
    if any(_is_sensitive_key(key) for key, _ in parse_qsl(parsed.query)):
        raise ValueError("url must not contain credential-like query parameters")
    if any(_is_sensitive_key(key) for key, _ in parse_qsl(parsed.fragment)):
        raise ValueError("url fragment must not contain credential-like parameters")
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("_", "").replace("-", "")
    sensitive_suffixes = (
        "apikey",
        "accesskey",
        "accesstoken",
        "authorization",
        "credential",
        "password",
        "secret",
        "signature",
        "token",
    )
    return normalized in _SENSITIVE_KEYS or normalized.endswith(sensitive_suffixes)


def _scrub_metadata(value: object, *, depth: int = 0) -> JsonValue:
    """Drop credential-shaped metadata and scrub credential query parameters."""
    if depth > 12:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            key: _scrub_metadata(item, depth=depth + 1)
            for key, item in value.items()
            if isinstance(key, str) and not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_scrub_metadata(item, depth=depth + 1) for item in value]
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            try:
                return _safe_url(value)
            except ValueError:
                return "[redacted-url]"

        def scrub(match: re.Match[str]) -> str:
            raw = match.group(0)
            suffix = "" if raw[-1:] not in ".,;:)]}" else raw[-1]
            target = raw[:-1] if suffix else raw
            try:
                return _safe_url(target) + suffix
            except ValueError:
                return "[redacted-url]" + suffix

        return _URL_RE.sub(scrub, value[:20_000])
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value == value and value not in (float("inf"), float("-inf")):
            return value
        return "[non-finite]"
    return "[unsupported]"


class BenchmarkCase(StrictModel):
    """Public case row; aliases accept the canonical query_gold `id`/`prompt` form."""

    case_id: CaseId = Field(
        validation_alias=AliasChoices("caseId", "case_id", "id"),
        serialization_alias="caseId",
    )
    query: Annotated[str, StringConstraints(min_length=1, max_length=8000)] = Field(
        validation_alias=AliasChoices("query", "prompt"),
        serialization_alias="query",
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class SearchResult(StrictModel):
    """One normalized search result with safe provider metadata."""

    rank: int | None = Field(default=None, ge=1)
    provider_rank: int | None = Field(default=None, ge=0, serialization_alias="providerRank")
    title: str = ""
    url: NonEmpty
    snippet: str = ""
    content: str | None = None
    summary: str | None = None
    markdown: str | None = None
    author: str | None = None
    published_at: str | None = Field(default=None, serialization_alias="publishedAt")
    score: float | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def validate_public_url(cls, value: str) -> str:
        return _safe_url(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def sanitize_metadata(cls, value: object) -> object:
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise ValueError("metadata must be an object")
        return _scrub_metadata(value)

    @field_validator("scores", mode="before")
    @classmethod
    def scores_must_be_finite(cls, value: object) -> object:
        if not isinstance(value, dict):
            raise ValueError("scores must be an object")
        normalized: dict[str, float] = {}
        for name, raw_score in value.items():
            if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
                raise ValueError("scores must be numeric")
            score = float(raw_score)
            if score != score or score in (float("inf"), float("-inf")):
                raise ValueError("scores must be finite")
            normalized[name] = score
        return normalized

    @field_validator("score", mode="before")
    @classmethod
    def score_is_finite(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("score must be numeric")
        score = float(value)
        if score != score or score in (float("inf"), float("-inf")):
            raise ValueError("scores must be finite")
        return score


class CostLineItem(StrictModel):
    """A provider-reported or reproducibly priced cost component."""

    name: NonEmpty
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price_usd: Decimal | None = Field(default=None, serialization_alias="unitPriceUsd")
    total_usd: Decimal | None = Field(default=None, serialization_alias="totalUsd")
    source: Literal["reported", "estimated", "unknown"]
    native: JsonValue | None = None

    @field_validator("quantity", "unit_price_usd", "total_usd", mode="before")
    @classmethod
    def parse_exact_decimal(cls, value: object) -> Decimal | None:
        return _decimal_from_json(value)

    @model_validator(mode="after")
    def validate_costs(self) -> CostLineItem:
        for value in (self.quantity, self.unit_price_usd, self.total_usd):
            if value is not None and (not value.is_finite() or value < 0):
                raise ValueError("cost quantities and amounts must be finite and non-negative")
        if self.source == "unknown" and any(
            value is not None for value in (self.unit_price_usd, self.total_usd)
        ):
            raise ValueError("unknown line items must not claim monetary costs")
        return self

    @field_validator("native", mode="before")
    @classmethod
    def sanitize_native(cls, value: object) -> object:
        if value is None:
            return None
        return _scrub_metadata(value)


class CostEvidence(StrictModel):
    """Native metering plus its price basis; missing values stay unknown."""

    reported_usd: Decimal | None = Field(default=None, serialization_alias="reportedUsd")
    estimated_usd: Decimal | None = Field(default=None, serialization_alias="estimatedUsd")
    source: Literal["reported", "estimated", "unknown"] = "unknown"
    native_usage: JsonValue | None = Field(default=None, serialization_alias="nativeUsage")
    price_snapshot: JsonValue | None = Field(default=None, serialization_alias="priceSnapshot")
    line_items: list[CostLineItem] = Field(default_factory=list, serialization_alias="lineItems")

    @model_validator(mode="before")
    @classmethod
    def accept_computed_total(cls, value: object) -> object:
        """Permit JSON round-trips containing the serialized computed total."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        supplied_total = data.pop("totalUsd", data.pop("total_usd", None))
        if supplied_total is not None:
            known_total = data.get("reportedUsd", data.get("reported_usd"))
            if known_total is None:
                known_total = data.get("estimatedUsd", data.get("estimated_usd"))
            if known_total is not None and str(known_total) != str(supplied_total):
                raise ValueError("totalUsd must match reportedUsd or estimatedUsd")
        return data

    @field_validator("reported_usd", "estimated_usd")
    @classmethod
    def validate_usd(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("USD costs must be finite and non-negative")
        return value

    @field_validator("reported_usd", "estimated_usd", mode="before")
    @classmethod
    def parse_exact_usd(cls, value: object) -> Decimal | None:
        return _decimal_from_json(value)

    @model_validator(mode="after")
    def reconcile_source(self) -> CostEvidence:
        resolved = (
            "reported"
            if self.reported_usd is not None
            else ("estimated" if self.estimated_usd is not None else "unknown")
        )
        if self.source != "unknown" and self.source != resolved:
            raise ValueError("source must match the reported or estimated total")
        if self.reported_usd is not None and self.estimated_usd is not None:
            raise ValueError("reported and estimated totals must remain separate")
        estimated_line_items = any(
            item.source == "estimated"
            and (item.unit_price_usd is not None or item.total_usd is not None)
            for item in self.line_items
        )
        if (self.estimated_usd is not None or estimated_line_items) and self.price_snapshot is None:
            raise ValueError("estimated cost requires a price snapshot")
        self.source = resolved  # type: ignore[assignment]
        return self

    @computed_field(return_type=Decimal | None, alias="totalUsd")  # type: ignore[prop-decorator]
    @property
    def total_usd(self) -> Decimal | None:
        """Return the reported total first, otherwise the preserved estimate."""
        return self.reported_usd if self.reported_usd is not None else self.estimated_usd

    @field_validator("native_usage", "price_snapshot", mode="before")
    @classmethod
    def sanitize_evidence(cls, value: object) -> object:
        if value is None:
            return None
        return _scrub_metadata(value)


class SearchResponse(StrictModel):
    """Provider-neutral response returned by a direct search adapter."""

    query: str
    provider: ProviderName
    results: list[SearchResult]
    total_results: int | None = Field(default=None, ge=0, serialization_alias="totalResults")
    provider_reported_latency_ms: float | None = Field(
        default=None, ge=0, serialization_alias="providerReportedLatencyMs"
    )
    provider_request_id: str | None = Field(default=None, serialization_alias="providerRequestId")
    cost: CostEvidence = Field(default_factory=CostEvidence)
    provider_metadata: dict[str, JsonValue] = Field(
        default_factory=dict, serialization_alias="providerMetadata"
    )

    @field_validator("provider_reported_latency_ms", mode="before")
    @classmethod
    def validate_provider_latency(cls, value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise TypeError("provider latency must be numeric")
        parsed = float(value)
        if parsed != parsed or parsed in (float("inf"), float("-inf")) or parsed < 0:
            raise ValueError("provider latency must be finite and non-negative")
        return parsed

    @field_validator("provider_metadata", mode="before")
    @classmethod
    def sanitize_provider_metadata(cls, value: object) -> object:
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise ValueError("providerMetadata must be an object")
        return _scrub_metadata(value)

    @field_validator("query")
    @classmethod
    def query_must_be_preserved(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class SafeSearchError(StrictModel):
    """Non-sensitive provider error summary suitable for durable run logs."""

    code: NonEmpty
    status_code: int | None = Field(default=None, ge=100, le=599, serialization_alias="statusCode")
    retryable: bool = False


class CaseResultRecord(StrictModel):
    """One terminal case result row in the append-only results JSONL."""

    schema_version: Literal["search-result/v1"] = Field(
        default="search-result/v1", serialization_alias="schemaVersion"
    )
    run_id: NonEmpty = Field(serialization_alias="runId")
    dataset_sha256: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$", serialization_alias="datasetSha256"
    )
    config_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        serialization_alias="configSha256",
    )
    case_id: CaseId = Field(serialization_alias="caseId")
    query: str
    query_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        serialization_alias="querySha256",
    )
    repetition: int = Field(ge=0)
    provider: ProviderName
    status: Literal["success", "error", "cancelled"]
    started_at: str = Field(serialization_alias="startedAt")
    finished_at: str = Field(serialization_alias="finishedAt")
    invocation_id: NonEmpty = Field(serialization_alias="invocationId")
    client_latency_ms: int = Field(ge=0, serialization_alias="clientLatencyMs")
    provider_reported_latency_ms: float | None = Field(
        default=None, ge=0, serialization_alias="providerReportedLatencyMs"
    )
    response: SearchResponse | None = None
    error: SafeSearchError | None = None
    attempt_ids: list[str] = Field(default_factory=list, serialization_alias="attemptIds")
    response_attempt_ids: list[str] = Field(
        default_factory=list, serialization_alias="responseAttemptIds"
    )
    cost_scope: Literal["response", "attempts", "unknown"] = Field(
        default="unknown", serialization_alias="costScope"
    )

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> CaseResultRecord:
        if self.query_sha256 != hashlib.sha256(self.query.encode("utf-8")).hexdigest():
            raise ValueError("querySha256 must match the exact query")
        if self.status == "success" and (self.response is None or self.error is not None):
            raise ValueError("success result requires a response and no error")
        if self.status != "success" and self.response is not None:
            raise ValueError("failed or cancelled result must not include a response")
        if self.status == "error" and self.error is None:
            raise ValueError("error result requires a safe error")
        if self.response is not None and (
            self.response.query != self.query or self.response.provider != self.provider
        ):
            raise ValueError("response query and provider must match the result row")
        return self

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value

    @field_validator("provider_reported_latency_ms", mode="before")
    @classmethod
    def validate_case_provider_latency(cls, value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise TypeError("provider latency must be numeric")
        parsed = float(value)
        if parsed != parsed or parsed in (float("inf"), float("-inf")) or parsed < 0:
            raise ValueError("provider latency must be finite and non-negative")
        return parsed


def parse_benchmark_case(value: object) -> BenchmarkCase:
    """Validate a public case without exposing invalid row contents in errors."""
    try:
        return BenchmarkCase.model_validate(value)
    except Exception:
        raise ValueError("invalid public benchmark case; expected only id and prompt") from None
