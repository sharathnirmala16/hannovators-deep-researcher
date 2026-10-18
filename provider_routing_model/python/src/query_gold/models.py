"""Strict schemas for canonical query/gold records and benchmark exports."""

from __future__ import annotations

import math
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import PurePosixPath
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from query_gold.paths import check_portable_path_component

SCHEMA_VERSION = "query-gold/v1"
MODEL_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{1,127}$"

CategoryId = Literal[
    "01_earnings_corporate_finance",
    "02_biomedical_clinical_trials",
    "03_code_api_documentation",
    "04_venture_capital_funding_ma",
    "05_government_courts_legal",
    "06_hardware_product_specifications",
    "07_static_mathematics_stem",
    "08_sports_box_scores_game_stats",
    "09_real_estate_land_registries",
    "10_academic_literature_citations",
    "11_cybersecurity_vulnerability_tracking",
    "12_municipal_code_zoning_local_law",
    "13_logistics_freight_supply_chain",
    "14_aerospace_telemetry_records",
    "15_cloud_infrastructure_service_pricing",
    "16_art_collectibles_auction_transactions",
    "17_local_graph_municipal_pois_directory_lookups",
    "18_entertainment_box_office_media_registries",
    "19_immigration_visa_bulletins_consular_policies",
    "20_historical_meteorology_disaster_telemetry",
    "21_gaming_software_release_patch_telemetry",
    "22_consumer_ecommerce_msrp_recall_notices",
    "23_executive_directory_corporate_leadership",
    "24_standards_rfcs_technical_specifications",
]
TemporalKind = Literal["immutable", "as_of", "period", "event", "version"]
TemporalPrecision = Literal["immutable", "year", "month", "day", "second", "version"]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CaseId = Annotated[str, StringConstraints(min_length=2, max_length=128, pattern=MODEL_ID_PATTERN)]

_DATE_PATTERNS = {
    "year": re.compile(r"^\d{4}$"),
    "month": re.compile(r"^\d{4}-\d{2}$"),
    "day": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "second": re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
        r"(?:Z|[+-]\d{2}:\d{2})$"
    ),
}
_SENSITIVE_QUERY_KEYS = {
    "access_key",
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
    "credentials",
    "key",
    "password",
    "secret",
    "signature",
    "sig",
    "token",
}
_SENSITIVE_PATH_NAMES = {
    ".netrc",
    ".npmrc",
    ".pypirc",
    "authorized_keys",
    "credential",
    "credentials",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
    "secret",
    "secrets",
    "secrets.json",
}


def _check_iso_date(value: str, precision: str) -> None:
    """Validate a date at exactly the precision claimed by its source."""
    pattern = _DATE_PATTERNS.get(precision)
    if pattern is None or not pattern.fullmatch(value):
        raise ValueError(f"date must use ISO {precision} precision")
    try:
        if precision == "year":
            year = int(value)
            if not 1 <= year <= 9999:
                raise ValueError("year is out of range")
        elif precision == "month":
            date.fromisoformat(f"{value}-01")
        elif precision == "day":
            date.fromisoformat(value)
        else:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if timestamp.utcoffset() is None:
                raise ValueError("second precision requires an explicit timezone")
    except ValueError as error:
        raise ValueError(f"invalid ISO {precision} date") from error


def _check_source_date(value: str) -> None:
    """Accept only source-supplied ISO dates without inventing missing precision."""
    for precision in ("year", "month", "day", "second"):
        if _DATE_PATTERNS[precision].fullmatch(value):
            _check_iso_date(value, precision)
            return
    raise ValueError("date must be YYYY, YYYY-MM, YYYY-MM-DD, or a zoned timestamp")


def _check_path_is_lexically_safe(value: str) -> None:
    """Reject unsafe evidence paths before any filesystem access is attempted."""
    if not value or "\x00" in value or "\\" in value:
        raise ValueError("rawPath must be a safe relative POSIX path")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError("rawPath must be relative to the category output directory")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        raise ValueError("rawPath must not be a URL or URI")

    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("rawPath must not contain empty, dot, or parent path components")
    for part in parts:
        check_portable_path_component(part)
        lowered = part.casefold()
        if lowered == ".env" or lowered.startswith(".env."):
            raise ValueError("rawPath must not reference .env credential files")
        if lowered in _SENSITIVE_PATH_NAMES:
            raise ValueError("rawPath must not reference credential files")
    if PurePosixPath(value).is_absolute():
        raise ValueError("rawPath must be relative")


def _check_public_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("url must not embed credentials")
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.casefold() in _SENSITIVE_QUERY_KEYS:
            raise ValueError("url must not contain credential-like query parameters")
    for key, _ in parse_qsl(parsed.fragment, keep_blank_values=True):
        if key.casefold() in _SENSITIVE_QUERY_KEYS:
            raise ValueError("url fragment must not contain credential-like parameters")
    return value


class StrictModel(BaseModel):
    """Base model for all persisted/external JSON boundaries."""

    model_config = ConfigDict(extra="forbid", strict=True, validate_default=True)


class TemporalScope(StrictModel):
    kind: TemporalKind
    precision: TemporalPrecision
    asOf: str | None = None
    date: str | None = None
    periodStart: str | None = None
    periodEnd: str | None = None
    version: NonEmpty | None = None
    immutableReason: NonEmpty | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> TemporalScope:
        supplied = {
            "asOf": self.asOf,
            "date": self.date,
            "periodStart": self.periodStart,
            "periodEnd": self.periodEnd,
            "version": self.version,
        }
        if self.kind == "immutable":
            if self.precision != "immutable":
                raise ValueError("immutable scope must use immutable precision")
            if any(value is not None for value in supplied.values()):
                raise ValueError("immutable scope must not include mutable scope fields")
            return self

        if self.precision in {"immutable", "version"} and self.kind != "version":
            raise ValueError(
                "mutable date scope must declare year, month, day, or second precision"
            )
        if self.immutableReason is not None:
            raise ValueError("immutableReason is only valid for immutable facts")

        expected_fields = {
            "as_of": {"asOf"},
            "event": {"date"},
            "period": {"periodStart", "periodEnd"},
            "version": {"version"},
        }[self.kind]
        missing = [name for name in expected_fields if supplied[name] is None]
        extras = [
            name
            for name, value in supplied.items()
            if value is not None and name not in expected_fields
        ]
        if missing:
            raise ValueError(f"{self.kind} scope requires {', '.join(sorted(missing))}")
        if extras:
            raise ValueError(f"{self.kind} scope cannot include {', '.join(sorted(extras))}")

        if self.kind == "version":
            if self.precision != "version":
                raise ValueError("version scope must use version precision")
            return self
        if self.precision == "version":
            raise ValueError("date scope cannot use version precision")

        scope_dates = [value for value in supplied.values() if value is not None]
        for value in scope_dates:
            _check_iso_date(value, self.precision)
        if (
            self.kind == "period"
            and self.periodStart is not None
            and self.periodEnd is not None
            and _date_sort_key(self.periodStart, self.precision)
            > _date_sort_key(self.periodEnd, self.precision)
        ):
            raise ValueError("periodStart must not be after periodEnd")
        return self


def _date_sort_key(value: str, precision: str) -> datetime:
    if precision == "year":
        return datetime(int(value), 1, 1)
    if precision == "month":
        year, month = (int(part) for part in value.split("-"))
        return datetime(year, month, 1)
    if precision == "day":
        parsed = date.fromisoformat(value)
        return datetime(parsed.year, parsed.month, parsed.day)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)


class GoldAnswer(StrictModel):
    answer: NonEmpty
    value: JsonValue | None = None
    acceptedAnswers: list[NonEmpty]
    units: NonEmpty | None = None
    currency: NonEmpty | None = None

    @field_validator("value")
    @classmethod
    def finite_json_value(cls, value: JsonValue | None) -> JsonValue | None:
        def check(node: JsonValue) -> None:
            if isinstance(node, float) and not math.isfinite(node):
                raise ValueError("gold.value numbers must be finite")
            if isinstance(node, list):
                for item in node:
                    check(item)
            elif isinstance(node, dict):
                for key, item in node.items():
                    if not isinstance(key, str):
                        raise ValueError("gold.value object keys must be strings")
                    check(item)

        if value is not None:
            check(value)
        return value

    @field_validator("acceptedAnswers")
    @classmethod
    def accepted_answers_are_unique(cls, answers: list[str]) -> list[str]:
        normalized = [" ".join(answer.casefold().split()) for answer in answers]
        if len(normalized) != len(set(normalized)):
            raise ValueError("acceptedAnswers must not contain duplicate normalized strings")
        return answers


class Evidence(StrictModel):
    url: str
    title: NonEmpty
    retrievedAtUTC: str
    publishedAt: str | None = None
    effectiveDate: str | None = None
    sourceRecordId: NonEmpty | None = None
    upstreamRevision: NonEmpty | None = None
    license: NonEmpty | None = None
    rawSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rawPath: str
    excerpt: Annotated[str, StringConstraints(min_length=1, max_length=8000)]

    @field_validator("url")
    @classmethod
    def public_url(cls, value: str) -> str:
        return _check_public_url(value)

    @field_validator("rawPath")
    @classmethod
    def safe_raw_path(cls, value: str) -> str:
        _check_path_is_lexically_safe(value)
        return value

    @field_validator("excerpt")
    @classmethod
    def excerpt_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("excerpt must not be blank")
        return value

    @field_validator("retrievedAtUTC")
    @classmethod
    def retrieved_at_is_explicit_utc(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value):
            raise ValueError("retrievedAtUTC must be a full UTC timestamp including seconds")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("retrievedAtUTC must be an ISO timestamp") from error
        if parsed.utcoffset() != timedelta(0):
            raise ValueError("retrievedAtUTC must be UTC")
        return value

    @field_validator("publishedAt", "effectiveDate")
    @classmethod
    def source_date_keeps_declared_precision(cls, value: str | None) -> str | None:
        if value is not None:
            _check_source_date(value)
        return value


class Derivation(StrictModel):
    sourceFamily: NonEmpty
    generatorVersion: NonEmpty
    questionType: NonEmpty


class QueryGoldCase(StrictModel):
    schemaVersion: Literal["query-gold/v1"]
    id: CaseId
    categoryId: CategoryId
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
    temporal: TemporalScope
    gold: GoldAnswer
    evidence: list[Evidence] = Field(min_length=1, max_length=20)
    derivation: Derivation

    @field_validator("schemaVersion")
    @classmethod
    def canonical_schema_version(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"schemaVersion must be {SCHEMA_VERSION}")
        return value


class PublicBenchmarkCase(StrictModel):
    """Answer-free, exact public benchmark input record."""

    id: CaseId
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PrivateBenchmarkAnswer(StrictModel):
    """Private reference answer; kept outside public benchmark inputs."""

    id: CaseId
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    answer: NonEmpty
    goldUrls: list[str] = Field(min_length=1)

    @field_validator("goldUrls")
    @classmethod
    def urls_are_public(cls, values: list[str]) -> list[str]:
        for value in values:
            _check_public_url(value)
        return values
