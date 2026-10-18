"""Shared helper utilities, allowlists, and constants for search providers."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import JsonValue

from search_urls.configuration import PricingConfig
from search_urls.transport import SearchProviderError

# ============================================================================
# Provider Constants & Strict Option Allowlists
# ============================================================================

# Exa
EXA_SEARCH_URL = "https://api.exa.ai/search"
EXA_ALLOWED_OPTIONS = frozenset(
    {
        "type",
        "contents",
        "category",
        "include_domains",
        "exclude_domains",
        "start_published_date",
        "end_published_date",
        "start_crawl_date",
        "end_crawl_date",
        "use_autoprompt",
        "user_location",
        "additional_queries",
        "moderation",
        "livecrawl",
        "livecrawl_timeout",
    }
)
EXA_VALID_TYPES = frozenset({"auto", "fast", "instant", "deep", "deep-lite", "deep-reasoning"})
EXA_CAMEL_KEYS: dict[str, str] = {
    "include_domains": "includeDomains",
    "exclude_domains": "excludeDomains",
    "start_published_date": "startPublishedDate",
    "end_published_date": "endPublishedDate",
    "start_crawl_date": "startCrawlDate",
    "end_crawl_date": "endCrawlDate",
    "additional_queries": "additionalQueries",
    "user_location": "userLocation",
    "livecrawl_timeout": "livecrawlTimeout",
    "use_autoprompt": "useAutoprompt",
}
EXA_BASE_RATES: dict[str, Decimal] = {
    "instant": Decimal("0.004"),
    "fast": Decimal("0.007"),
    "auto": Decimal("0.007"),
    "deep-lite": Decimal("0.012"),
    "deep": Decimal("0.012"),
    "deep-reasoning": Decimal("0.015"),
}

# Tavily
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_CREDIT_USD = Decimal("0.008")  # PAYGO reference
TAVILY_ALLOWED_OPTIONS = frozenset(
    {
        "search_depth",
        "topic",
        "include_answer",
        "include_raw_content",
        "include_images",
        "include_image_descriptions",
        "include_domains",
        "exclude_domains",
        "time_range",
        "days",
        "max_tokens",
    }
)
TAVILY_VALID_DEPTHS = frozenset({"basic", "advanced", "fast", "ultra-fast"})
TAVILY_VALID_TOPICS = frozenset({"general", "news", "finance"})

# Brave
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_COST_PER_REQUEST = Decimal("0.005")  # $5 per 1,000 requests
BRAVE_ALLOWED_OPTIONS = frozenset(
    {
        "country",
        "search_lang",
        "ui_lang",
        "freshness",
        "safesearch",
        "spellcheck",
        "offset",
        "text_decorations",
        "result_filter",
        "units",
        "goggles",
        "extra_snippets",
        "summary",
        "enable_rich_callback",
        "include_fetch_metadata",
        "operators",
        "no_cache",
        "api_version",
        "location",
    }
)
BRAVE_LOCATION_HEADERS: dict[str, str] = {
    "latitude": "X-Loc-Lat",
    "longitude": "X-Loc-Long",
    "timezone": "X-Loc-Timezone",
    "city": "X-Loc-City",
    "state": "X-Loc-State",
    "state_name": "X-Loc-State-Name",
    "country": "X-Loc-Country",
    "postal_code": "X-Loc-Postal-Code",
}
BRAVE_NON_QUERY_OPTIONS = frozenset({"no_cache", "api_version", "location"})

# Firecrawl
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"
FIRECRAWL_CREDIT_RATE = Decimal("0.0038")  # $19 per 5,000 monthly credits reference
FIRECRAWL_ALLOWED_OPTIONS = frozenset(
    {
        "include_domains",
        "exclude_domains",
        "scrape_options",
        "threat_protection",
        "risk_score_threshold",
        "blocked_tlds",
        "failure_policy",
        "tool_detail",
        "formats",
        "only_main_content",
        "only_clean_content",
        "include_tags",
        "exclude_tags",
        "max_age",
        "min_age",
        "wait_for",
        "skip_tls_verification",
        "remove_base64_images",
        "block_ads",
        "store_in_cache",
        "zero_data_retention",
        "check_prompt_injection",
        "redact_pii",
        "save_changes",
        "full_page",
        "page_markers",
        "max_pages",
    }
)
FIRECRAWL_CAMEL_KEYS: dict[str, str] = {
    "include_domains": "includeDomains",
    "exclude_domains": "excludeDomains",
    "scrape_options": "scrapeOptions",
    "threat_protection": "threatProtection",
    "risk_score_threshold": "riskScoreThreshold",
    "blocked_tlds": "blockedTlds",
    "failure_policy": "failurePolicy",
    "tool_detail": "toolDetail",
    "only_main_content": "onlyMainContent",
    "only_clean_content": "onlyCleanContent",
    "include_tags": "includeTags",
    "exclude_tags": "excludeTags",
    "max_age": "maxAge",
    "min_age": "minAge",
    "wait_for": "waitFor",
    "skip_tls_verification": "skipTlsVerification",
    "remove_base64_images": "removeBase64Images",
    "block_ads": "blockAds",
    "store_in_cache": "storeInCache",
    "zero_data_retention": "zeroDataRetention",
    "check_prompt_injection": "checkPromptInjection",
    "redact_pii": "redactPii",
    "save_changes": "saveChanges",
    "full_page": "fullPage",
    "page_markers": "pageMarkers",
    "max_pages": "maxPages",
}


def _validate_tavily_pricing(pricing: PricingConfig, key: str | None) -> None:
    if pricing.rate_per_request is not None or pricing.rates:
        raise SearchProviderError("tavily", "configuration_error", retryable=False)
    if key is None and pricing.mode is not None and pricing.mode.lower() not in {"keyless", "free"}:
        raise SearchProviderError("tavily", "configuration_error", retryable=False)
    if key is not None and pricing.mode is not None and pricing.mode.lower() in {"keyless", "free"}:
        raise SearchProviderError("tavily", "configuration_error", retryable=False)


def _validate_brave_pricing(pricing: PricingConfig) -> None:
    if pricing.usd_per_credit is not None or pricing.rates:
        raise SearchProviderError("brave", "configuration_error", retryable=False)


def _validate_firecrawl_pricing(pricing: PricingConfig) -> None:
    if pricing.rate_per_request is not None or pricing.rates:
        raise SearchProviderError("firecrawl", "configuration_error", retryable=False)


def _validate_exa_pricing(pricing: PricingConfig) -> None:
    if pricing.usd_per_credit is not None:
        raise SearchProviderError("exa", "configuration_error", retryable=False)
    if pricing.rates:
        for rate_key, rate_val in pricing.rates.items():
            if rate_key not in EXA_VALID_TYPES:
                raise SearchProviderError("exa", "configuration_error", retryable=False)
            try:
                dec = Decimal(str(rate_val))
                if dec < 0:
                    raise SearchProviderError("exa", "configuration_error", retryable=False)
            except (InvalidOperation, TypeError):
                raise SearchProviderError("exa", "configuration_error", retryable=False) from None


def validate_provider_pricing(
    provider: str, pricing: PricingConfig | None, key: str | None = None
) -> None:
    """Validate provider pricing fields, non-negative values, and mode consistency."""
    if pricing is None:
        return

    if pricing.usd_per_credit is not None and pricing.usd_per_credit < 0:
        raise SearchProviderError(provider, "configuration_error", retryable=False)
    if pricing.rate_per_request is not None and pricing.rate_per_request < 0:
        raise SearchProviderError(provider, "configuration_error", retryable=False)

    if provider == "tavily":
        _validate_tavily_pricing(pricing, key)
    elif provider == "brave":
        _validate_brave_pricing(pricing)
    elif provider == "firecrawl":
        _validate_firecrawl_pricing(pricing)
    elif provider == "exa":
        _validate_exa_pricing(pricing)


def build_price_snapshot(
    provider: str,
    pricing: PricingConfig | None,
    *,
    default_plan: str,
    wire_mode: str | None = None,
    extra: dict[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    """Construct complete price snapshot preserving configured provenance and wire mode."""
    snapshot: dict[str, JsonValue] = {}
    if wire_mode is not None:
        snapshot["wire_mode"] = wire_mode

    if pricing is not None:
        snapshot["plan"] = pricing.plan or default_plan
        if pricing.mode is not None:
            snapshot["mode"] = pricing.mode
        elif wire_mode is not None:
            snapshot["mode"] = wire_mode
        if pricing.as_of is not None:
            snapshot["as_of"] = pricing.as_of
        if pricing.version is not None:
            snapshot["version"] = pricing.version
        if pricing.basis is not None:
            snapshot["basis"] = pricing.basis
        if pricing.rates:
            snapshot["rates"] = {
                k: str(v) if isinstance(v, Decimal) else v for k, v in pricing.rates.items()
            }
    else:
        snapshot["plan"] = default_plan
        if wire_mode is not None:
            snapshot["mode"] = wire_mode

    if extra:
        snapshot.update(extra)
    return snapshot


def clean_str(value: object) -> str | None:
    """Strip string whitespace or return None if empty/non-string."""
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return None


def to_finite_float(value: object) -> float | None:
    """Safely convert number or numeric string to finite float, returning None on invalid."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    if isinstance(value, str):
        try:
            val = float(value)
            return val if math.isfinite(val) else None
        except (ValueError, TypeError):
            return None
    return None


def check_payload_status(provider: str, payload: object) -> dict[str, object]:
    """Ensure HTTP 200 payload is a dict and does not contain semantic failure."""
    if not isinstance(payload, dict):
        raise SearchProviderError(provider, "invalid_response", status_code=200, retryable=True)
    if payload.get("success") is False:
        raise SearchProviderError(provider, "provider_error", status_code=200, retryable=True)
    if payload.get("error"):
        raise SearchProviderError(provider, "provider_error", status_code=200, retryable=True)
    if payload.get("status") in {"error", "failed", "failure"}:
        raise SearchProviderError(provider, "provider_error", status_code=200, retryable=True)
    if payload.get("type") == "ErrorResponse":
        raise SearchProviderError(provider, "provider_error", status_code=200, retryable=True)
    return payload


def extract_scores(raw: dict[str, Any]) -> tuple[float | None, dict[str, float]]:
    """Extract single score and full finite native scores map."""
    scores: dict[str, float] = {}
    raw_scores = raw.get("scores")
    if isinstance(raw_scores, dict):
        for k, v in raw_scores.items():
            fv = to_finite_float(v)
            if fv is not None:
                scores[str(k)] = fv

    single_score = to_finite_float(raw.get("score"))
    if single_score is not None and "score" not in scores:
        scores["score"] = single_score

    return single_score, scores


def firecrawl_wire(value: object) -> object:
    """Recursively map snake_case options to camelCase for Firecrawl wire format."""
    if isinstance(value, list):
        return [firecrawl_wire(it) for it in value]
    if isinstance(value, dict):
        return {FIRECRAWL_CAMEL_KEYS.get(k, k): firecrawl_wire(v) for k, v in value.items()}
    return value
