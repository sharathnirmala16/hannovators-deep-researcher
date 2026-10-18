"""Strict search-collection config model and JSON loader."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    Field,
    JsonValue,
    StringConstraints,
    ValidationError,
    field_validator,
)

from query_gold.io import ensure_safe_path
from search_urls.models import ProviderName, StrictModel

NonEmpty = Annotated[str, StringConstraints(min_length=1)]
_FORBIDDEN_KEYS = frozenset(
    {
        "accesskey",
        "accesstoken",
        "apikey",
        "authorization",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
    }
)
_FORBIDDEN_SUFFIXES = (
    "apikey",
    "accesskey",
    "accesstoken",
    "authtoken",
    "authorization",
    "credential",
    "credentials",
    "password",
    "secret",
    "signature",
    "token",
)


class RateLimit(StrictModel):
    """One fixed-window request allowance shared by a provider run."""

    requests: int = Field(ge=1)
    window_ms: int = Field(
        validation_alias=AliasChoices("windowMs", "window_ms"),
        serialization_alias="windowMs",
        ge=1,
    )


class SearchLimits(StrictModel):
    """Per-request, per-query, and retry bounds from the selected preset."""

    request_timeout_ms: int = Field(
        default=30_000,
        validation_alias=AliasChoices("requestTimeoutMs", "request_timeout_ms"),
        serialization_alias="requestTimeoutMs",
        ge=1,
    )
    query_timeout_ms: int = Field(
        default=120_000,
        validation_alias=AliasChoices("queryTimeoutMs", "query_timeout_ms"),
        serialization_alias="queryTimeoutMs",
        ge=1,
    )
    max_requests_per_query: int = Field(
        default=20,
        validation_alias=AliasChoices("maxRequestsPerQuery", "max_requests_per_query"),
        serialization_alias="maxRequestsPerQuery",
        ge=1,
    )
    max_retries: int = Field(
        default=1,
        validation_alias=AliasChoices("maxRetries", "max_retries"),
        serialization_alias="maxRetries",
        ge=0,
        le=1,
    )


class PricingConfig(StrictModel):
    """Optional runtime price override pinned with the provider preset."""

    plan: str | None = None
    mode: str | None = None
    usd_per_credit: Decimal | None = Field(
        default=None,
        validation_alias=AliasChoices("usdPerCredit", "usd_per_credit"),
        serialization_alias="usdPerCredit",
    )
    rate_per_request: Decimal | None = Field(
        default=None,
        validation_alias=AliasChoices("ratePerRequest", "rate_per_request"),
        serialization_alias="ratePerRequest",
    )
    rates: dict[str, JsonValue] = Field(default_factory=dict)
    as_of: str | None = Field(
        default=None,
        validation_alias=AliasChoices("asOf", "as_of"),
        serialization_alias="asOf",
    )
    version: str | None = None
    basis: str | None = None

    @field_validator("usd_per_credit", "rate_per_request", mode="before")
    @classmethod
    def parse_exact_price(cls, value: object) -> Decimal | None:
        if value is None or isinstance(value, Decimal):
            parsed = value
        elif isinstance(value, bool):
            raise TypeError("price must not be boolean")
        elif isinstance(value, (str, int, float)):
            try:
                parsed = Decimal(str(value))
            except InvalidOperation:
                raise ValueError("price must be a decimal") from None
        else:
            raise TypeError("price must be a decimal string or number")
        if parsed is not None and (not parsed.is_finite() or parsed < 0):
            raise ValueError("price must be finite and non-negative")
        return parsed


class SearchConfig(StrictModel):
    """Resolved provider preset used for one direct search collection run."""

    schema_version: Literal["search-collection-config/v1"] = Field(
        validation_alias=AliasChoices("schemaVersion", "schema_version"),
        serialization_alias="schemaVersion",
    )
    provider: ProviderName
    limit: int = Field(default=5, ge=1, le=100)
    options: dict[str, JsonValue] = Field(default_factory=dict)
    rate_limits: list[RateLimit] = Field(
        default_factory=lambda: [RateLimit(requests=10, window_ms=60_000)],
        validation_alias=AliasChoices("rateLimits", "rate_limits"),
        serialization_alias="rateLimits",
        min_length=1,
    )
    max_concurrency: int = Field(
        default=1,
        validation_alias=AliasChoices("maxConcurrency", "max_concurrency"),
        serialization_alias="maxConcurrency",
        ge=1,
    )
    limits: SearchLimits = Field(default_factory=SearchLimits)
    pricing: PricingConfig | None = None

    @field_validator("options", "pricing", mode="before")
    @classmethod
    def reject_secret_options(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("options and pricing must be objects")
        if _contains_forbidden_key(value):
            raise ValueError("provider settings must not include credentials")
        return value


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                return True
            normalized = "".join(character for character in key.casefold() if character.isalnum())
            if normalized in _FORBIDDEN_KEYS or normalized.endswith(_FORBIDDEN_SUFFIXES):
                return True
            if _contains_forbidden_key(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _is_credential_path(path: Path) -> bool:
    for part in path.parts:
        lowered = part.casefold()
        if lowered == ".env" or lowered.startswith(".env."):
            return True
    return False


def load_config(path: Path) -> SearchConfig:
    """Load JSON config after guarding credential paths and rejecting loose schemas."""
    if _is_credential_path(path):
        raise ValueError("configuration path is not allowed")
    try:
        safe_path = ensure_safe_path(path, require_existing=True)
        raw = json.loads(safe_path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
        return SearchConfig.model_validate(raw)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValidationError,
        ValueError,
    ):
        raise ValueError("invalid search collection config") from None


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value {value}")
