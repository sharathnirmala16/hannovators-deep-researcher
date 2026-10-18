"""Direct search adapters for Keenable, Parallel, Tinyfish, and You.com."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, cast

from pydantic import JsonValue, ValidationError

from search_urls.configuration import PricingConfig, SearchConfig
from search_urls.models import CostEvidence, CostLineItem, SearchResponse, SearchResult
from search_urls.transport import SearchProviderError, observation_for

_PRICING_VERSION = "FreeSearch LIMITS.md pricing snapshot (2026-10-05)"
_PRICING_AS_OF = "2026-10-05"
_PRICING_SOURCES = [
    ".archive/freesearch/LIMITS.md",
    ".archive/freesearch/freesearch-ui/src/features/quota/model/documentedProviderPrices.ts",
]

type _OptionRule = type[Any] | dict[str, Any] | tuple[str, Any, Any] | tuple[str, tuple[str, ...]]


def _integer(minimum: int | None = None, maximum: int | None = None) -> tuple[str, Any, Any]:
    return ("int", minimum, maximum)


def _enum(*values: str) -> tuple[str, tuple[str, ...]]:
    return ("enum", values)


def _string_list() -> tuple[str, Any, Any]:
    return ("string_list", None, None)


def _enum_list(*values: str) -> tuple[str, Any, Any]:
    return ("enum_list", values, None)


_OPTION_SCHEMAS: dict[str, dict[str, _OptionRule]] = {
    "keenable": {
        "mode": _enum("pro", "realtime"),
        "site": str,
        "acquired_after": str,
        "acquired_before": str,
        "published_after": str,
        "published_before": str,
        "query_time": str,
        "snippet_max_length": _integer(180, 10_000),
    },
    "parallel": {
        "mode": _enum("turbo", "fast", "basic", "advanced"),
        "max_chars_total": _integer(1),
        "session_id": str,
        "client_model": str,
        "advanced_settings": {
            "source_policy": {
                "include_domains": _string_list(),
                "exclude_domains": _string_list(),
                "after_date": str,
            },
            "fetch_policy": {
                "max_age_seconds": _integer(600),
                "timeout_seconds": _integer(1),
                "disable_cache_fallback": bool,
            },
            "excerpt_settings": {"max_chars_per_result": _integer(1)},
            "location": str,
            "max_results": _integer(1),
        },
    },
    "tinyfish": {
        "purpose": str,
        "location": str,
        "language": str,
        "include_domains": _string_list(),
        "exclude_domains": _string_list(),
        "recency_minutes": _integer(1, 5_256_000),
        "after_date": str,
        "before_date": str,
        "domain_type": _enum("web", "news", "research_paper"),
        "pub_year_min": _integer(0, 9999),
        "pub_year_max": _integer(0, 9999),
        "page": _integer(0, 10),
    },
    "you": {
        "freshness": str,
        "offset": _integer(0, 9),
        "country": str,
        "language": str,
        "safesearch": _enum("off", "moderate", "strict"),
        "knowledge": _enum("core"),
        "include_domains": _string_list(),
        "exclude_domains": _string_list(),
        "boost_domains": _string_list(),
        "strict_operators": bool,
        "extraction": {
            "mode": _enum("highlights", "full_page"),
            "source": _enum("blend", "cache", "fetch"),
            "highlights": {"total_max_tokens": _integer(1024, 8192)},
            "full_page": {"extraction_formats": _enum_list("html", "markdown")},
        },
        "crawl_timeout": _integer(1, 60),
        "livecrawl": _enum("web", "news", "all"),
        "livecrawl_formats": _enum_list("html", "markdown"),
    },
}

_RESULT_METADATA: dict[str, frozenset[str]] = {
    "keenable": frozenset(
        {
            "source",
            "site_name",
            "domain",
            "position",
            "rank",
            "date",
            "published_date",
            "publisher",
            "authors",
            "venue",
            "year",
            "cited_by_count",
            "pdf_url",
            "favicon_url",
            "thumbnail_url",
        }
    ),
    "parallel": frozenset(
        {
            "source",
            "site_name",
            "domain",
            "position",
            "rank",
            "publish_date",
            "authors",
            "excerpts",
        }
    ),
    "tinyfish": frozenset(
        {
            "site_name",
            "domain",
            "position",
            "rank",
            "date",
            "publish_date",
            "published_date",
            "publisher",
            "authors",
            "venue",
            "year",
            "cited_by_count",
            "pdf_url",
            "favicon_url",
            "thumbnail_url",
        }
    ),
    "you": frozenset(
        {
            "site_name",
            "domain",
            "position",
            "rank",
            "publish_date",
            "published_date",
            "publisher",
            "authors",
            "venue",
            "year",
            "cited_by_count",
            "pdf_url",
            "favicon_url",
            "thumbnail_url",
        }
    ),
}


def _option_error(provider: str) -> SearchProviderError:
    return SearchProviderError(provider, "invalid_options")


def _validate_mapping(
    provider: str,
    value: object,
    schema: dict[str, _OptionRule],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _option_error(provider)
    if any(not isinstance(key, str) or key not in schema for key in value):
        raise _option_error(provider)
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if item is None:
            continue
        rule = schema[key]
        if isinstance(rule, dict):
            cleaned[key] = _validate_mapping(provider, item, rule)
        elif not _valid_option(item, rule):
            raise _option_error(provider)
        else:
            cleaned[key] = item
    return cleaned


def _valid_option(value: object, rule: _OptionRule) -> bool:
    if rule is str:
        return isinstance(value, str)
    if rule is bool:
        return type(value) is bool
    if isinstance(rule, tuple) and len(rule) == 2 and rule[0] == "enum":
        choices = rule[1]
        return isinstance(value, str) and isinstance(choices, tuple) and value in choices
    if isinstance(rule, tuple) and len(rule) == 3 and rule[0] == "int":
        if type(value) is not int:
            return False
        minimum, maximum = rule[1], rule[2]
        return not (
            (minimum is not None and (not isinstance(minimum, int) or value < minimum))
            or (maximum is not None and (not isinstance(maximum, int) or value > maximum))
        )
    if isinstance(rule, tuple) and len(rule) == 3 and rule[0] == "string_list":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if isinstance(rule, tuple) and len(rule) == 3 and rule[0] == "enum_list":
        choices = rule[1]
        return isinstance(value, list) and all(
            isinstance(item, str) and isinstance(choices, tuple) and item in choices
            for item in value
        )
    return False


def _options(config: SearchConfig) -> dict[str, Any]:
    return _validate_mapping(config.provider, config.options, _OPTION_SCHEMAS[config.provider])


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _nonnegative_decimal(value: object) -> Decimal | None:
    number = _positive_number(value)
    if number is None or number < 0:
        return None
    return Decimal(str(value))


def _date(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        from datetime import date, datetime

        parsed_datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed_datetime.isoformat()
    except ValueError:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None


def _safe_metadata_value(value: object) -> JsonValue | None:
    if value is None or isinstance(value, (str, bool, int)):
        return value if not isinstance(value, str) or len(value) <= 20_000 else value[:20_000]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, list) and len(value) <= 100:
        safe_values: list[JsonValue] = []
        for item in value:
            if isinstance(item, (str, bool, int)):
                safe_values.append(item[:20_000] if isinstance(item, str) else item)
            elif isinstance(item, float) and math.isfinite(item):
                safe_values.append(item)
            else:
                return None
        return safe_values
    return None


def _rank(item: dict[str, object]) -> int | None:
    for key in ("position", "rank"):
        value = item.get(key)
        if type(value) is int and value >= 1:
            return value
    return None


def _scores(item: dict[str, object]) -> tuple[float | None, dict[str, float]]:
    scores: dict[str, float] = {}
    raw = item.get("scores")
    if isinstance(raw, dict):
        for key, value in raw.items():
            parsed = _positive_number(value)
            if isinstance(key, str) and parsed is not None:
                scores[key[:80]] = parsed
    for key in ("score", "relevance_score", "rank_score"):
        parsed = _positive_number(item.get(key))
        if parsed is not None:
            scores.setdefault(key, parsed)
    score = _positive_number(item.get("score"))
    return score, scores


def _normalize_result(
    provider: str,
    value: object,
    *,
    section: str | None = None,
) -> SearchResult | None:
    if not isinstance(value, dict):
        return None
    raw_url = value.get("url", value.get("link"))
    if not isinstance(raw_url, str) or not raw_url:
        return None
    title = value.get("title", value.get("name"))
    snippet = _result_snippet(provider, value)

    metadata: dict[str, JsonValue] = {}
    for key in _RESULT_METADATA[provider]:
        if key in value:
            safe_value = _safe_metadata_value(value[key])
            if safe_value is not None:
                metadata[key] = safe_value
    if section is not None:
        metadata["section"] = section

    rank = _rank(value)
    score, scores = _scores(value)
    published_at = next(
        (
            parsed
            for key in ("published_at", "publish_date", "published_date", "date")
            if (parsed := _date(value.get(key))) is not None
        ),
        None,
    )
    kwargs: dict[str, Any] = {
        "url": raw_url,
        "title": title if isinstance(title, str) else "",
        "snippet": snippet if isinstance(snippet, str) else "",
        "metadata": metadata,
        "score": score,
        "scores": scores,
        "published_at": published_at,
    }
    if rank is not None:
        kwargs["rank"] = rank
        kwargs["provider_rank"] = rank
    for field in ("content", "summary", "markdown", "author"):
        raw = value.get(field)
        if isinstance(raw, str):
            kwargs[field] = raw[:50_000]
    try:
        return SearchResult.model_validate(kwargs)
    except ValidationError:
        return None


def _result_snippet(provider: str, value: dict[str, object]) -> str:
    snippet = value.get("snippet", value.get("description"))
    if not isinstance(snippet, str):
        snippet = value.get("content") if isinstance(value.get("content"), str) else ""
    if provider == "parallel":
        excerpts = value.get("excerpts")
        if isinstance(excerpts, list) and all(isinstance(item, str) for item in excerpts):
            return "\n\n".join(excerpts)
    if provider == "you":
        snippets = value.get("snippets")
        if isinstance(snippets, list) and snippets and isinstance(snippets[0], str):
            return snippets[0]
    return snippet if isinstance(snippet, str) else ""


def _reported_latency(payload: dict[str, object]) -> float | None:
    for key in ("latency_ms", "duration_ms", "response_time_ms"):
        value = _positive_number(payload.get(key))
        if value is not None and value >= 0:
            return value
    for key in ("latency_seconds", "duration_seconds"):
        value = _positive_number(payload.get(key))
        if value is not None and value >= 0:
            return value * 1000
    value = _positive_number(payload.get("latency"))
    unit = payload.get("latency_unit")
    if value is not None and unit in {"ms", "milliseconds"}:
        return value
    if value is not None and unit in {"s", "seconds"}:
        return value * 1000
    return None


def _provider_metadata(payload: dict[str, object]) -> dict[str, JsonValue]:
    metadata: dict[str, JsonValue] = {}
    for key in ("request_id", "search_id", "query_id"):
        value = payload.get(key)
        if isinstance(value, str) and value and len(value) <= 200:
            metadata[key] = value
    latency = _reported_latency(payload)
    if latency is not None:
        metadata["latency_ms"] = latency
    return metadata


def _ensure_search_payload(provider: str, payload: dict[str, object]) -> None:
    status = payload.get("status")
    error = payload.get("error")
    errors = payload.get("errors")
    if payload.get("success") is False or (
        isinstance(status, str) and status.casefold() in {"error", "failed", "failure"}
    ):
        raise SearchProviderError(provider, "semantic_error", retryable=True)
    if error not in (None, "", [], {}):
        raise SearchProviderError(provider, "semantic_error", retryable=True)
    if errors not in (None, "", [], {}):
        raise SearchProviderError(provider, "semantic_error", retryable=True)


def _raw_results(provider: str, payload: dict[str, object]) -> list[tuple[object, str | None]]:
    raw = payload.get("results")
    if provider == "you" and isinstance(raw, dict):
        items: list[tuple[object, str | None]] = []
        for section in ("web", "news"):
            values = raw.get(section)
            if values is not None and not isinstance(values, list):
                raise SearchProviderError(provider, "invalid_response", retryable=True)
            if isinstance(values, list):
                items.extend((item, section) for item in values)
        return items
    if not isinstance(raw, list):
        raise SearchProviderError(provider, "invalid_response", retryable=True)
    return [(item, None) for item in raw]


def _normalize_top_results(
    provider: str,
    raw_results: list[tuple[object, str | None]],
    limit: int,
    provider_metadata: dict[str, JsonValue],
) -> list[SearchResult]:
    results: list[SearchResult] = []
    rejected: list[JsonValue] = []
    for index, (raw, section) in enumerate(raw_results):
        if len(results) >= limit:
            break
        result = _normalize_result(provider, raw, section=section)
        if result is None:
            item = raw if isinstance(raw, dict) else {}
            rejection: dict[str, JsonValue] = {
                "index": index + 1,
                "code": "invalid_result",
                "providerRank": _rank(item) or index + 1,
            }
            rejected.append(rejection)
            continue
        native_rank = _rank(raw) if isinstance(raw, dict) else None
        result.rank = len(results) + 1
        result.provider_rank = native_rank if native_rank is not None else index + 1
        results.append(result)
    if raw_results and not results:
        raise SearchProviderError(provider, "invalid_response", retryable=True)
    if rejected:
        provider_metadata["rejected_results"] = rejected
    return results


def _total_results(payload: dict[str, object], received: int) -> int:
    value = payload.get("total_results")
    if type(value) is int and value >= 0:
        return value
    return received


def _price_component(
    name: str,
    unit: str,
    rate: Decimal | None,
    basis: str,
) -> dict[str, JsonValue]:
    return {
        "name": name,
        "unit": unit,
        "unitPriceUsd": float(rate) if rate is not None else None,
        "basis": basis,
    }


def _validate_pricing(config: SearchConfig) -> None:
    pricing = config.pricing
    if pricing is None:
        return
    allowed = {
        "keenable": {"request", "credit"},
        "parallel": {"request", "extra_result"},
        "tinyfish": {"request"},
        "you": {"request", "live_page"},
    }[config.provider]
    for name, value in pricing.rates.items():
        if name not in allowed or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SearchProviderError(config.provider, "invalid_pricing")
        rate = Decimal(str(value))
        if not rate.is_finite() or rate < 0:
            raise SearchProviderError(config.provider, "invalid_pricing")
    if pricing.usd_per_credit is not None and config.provider != "keenable":
        raise SearchProviderError(config.provider, "invalid_pricing")
    direct_rates: dict[str, Decimal] = {}
    if pricing.rate_per_request is not None:
        direct_rates["request"] = pricing.rate_per_request
    if pricing.usd_per_credit is not None:
        direct_rates["credit"] = pricing.usd_per_credit
    for name, direct_rate in direct_rates.items():
        configured_rate = pricing.rates.get(name)
        if configured_rate is not None:
            if isinstance(configured_rate, bool) or not isinstance(configured_rate, (int, float)):
                raise SearchProviderError(config.provider, "invalid_pricing")
            if Decimal(str(configured_rate)) != direct_rate:
                raise SearchProviderError(config.provider, "invalid_pricing")
    if pricing.mode is not None:
        valid_modes = {
            "keenable": {"pro", "realtime"},
            "parallel": {"turbo", "fast", "basic", "advanced"},
            "tinyfish": set(),
            "you": set(),
        }[config.provider]
        if pricing.mode not in valid_modes:
            raise SearchProviderError(config.provider, "invalid_pricing")


def _price_rate(
    config: SearchConfig,
    provider: str,
    name: str,
    default: Decimal | None,
) -> Decimal | None:
    pricing: PricingConfig | None = config.pricing
    if pricing is not None:
        if name in pricing.rates:
            value = pricing.rates[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SearchProviderError(provider, "invalid_pricing")
            rate = Decimal(str(value))
            if not rate.is_finite() or rate < 0:
                raise SearchProviderError(provider, "invalid_pricing")
            return rate
        if provider == "keenable" and name == "credit" and pricing.usd_per_credit is not None:
            return pricing.usd_per_credit
        if name == "request" and pricing.rate_per_request is not None:
            return pricing.rate_per_request
    return default


def _price_snapshot(
    config: SearchConfig,
    provider: str,
    mode: str,
    components: list[dict[str, JsonValue]],
) -> dict[str, JsonValue]:
    pricing = config.pricing
    updated: list[dict[str, JsonValue]] = []
    for component in components:
        copy = dict(component)
        name = component["name"]
        if isinstance(name, str):
            default_value = component.get("unitPriceUsd")
            default_rate = (
                Decimal(str(default_value)) if isinstance(default_value, (int, float)) else None
            )
            rate = _price_rate(config, provider, name, default_rate)
            copy["unitPriceUsd"] = float(rate) if rate is not None else None
        if pricing is not None and pricing.basis is not None:
            copy["basis"] = pricing.basis
        updated.append(copy)
    snapshot: dict[str, JsonValue] = {
        "provider": provider,
        "operation": "search",
        "mode": mode,
        "version": (
            pricing.version
            if pricing is not None and pricing.version is not None
            else _PRICING_VERSION
        ),
        "asOf": (
            pricing.as_of if pricing is not None and pricing.as_of is not None else _PRICING_AS_OF
        ),
        "sourceFiles": cast(JsonValue, _PRICING_SOURCES.copy()),
        "components": cast(JsonValue, updated),
    }
    if pricing is not None and pricing.plan is not None:
        snapshot["plan"] = pricing.plan
    return snapshot


def _validate_wire_mode(config: SearchConfig, mode: str) -> None:
    pricing = config.pricing
    if pricing is not None and pricing.mode is not None and pricing.mode != mode:
        raise SearchProviderError(config.provider, "invalid_pricing")


def _line(
    name: str,
    quantity: Decimal | None,
    unit: str,
    unit_price: Decimal | None,
    source: Literal["reported", "estimated", "unknown"],
    *,
    native: JsonValue | None = None,
) -> CostLineItem:
    total = quantity * unit_price if quantity is not None and unit_price is not None else None
    return CostLineItem(
        name=name,
        quantity=quantity,
        unit=unit,
        unit_price_usd=unit_price,
        total_usd=total,
        source=source,
        native=native,
    )


def _response(
    config: SearchConfig,
    query: str,
    raw_payload: dict[str, object],
    results: list[SearchResult],
    cost: CostEvidence,
    provider_metadata: dict[str, JsonValue],
    received: int,
) -> SearchResponse:
    observation = observation_for(raw_payload)
    merged_cost = _merge_observation(cost, observation)
    request_id = None
    for key in ("request_id", "search_id", "query_id"):
        candidate = provider_metadata.get(key)
        if isinstance(candidate, str):
            request_id = candidate
            break
    if request_id is None and observation is not None:
        request_id = observation.request_id
    return SearchResponse(
        query=query,
        provider=config.provider,
        results=results,
        total_results=_total_results(raw_payload, received),
        provider_reported_latency_ms=_reported_latency(raw_payload),
        provider_request_id=request_id,
        cost=merged_cost,
        provider_metadata=provider_metadata,
    )


def _observation_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed >= 0 else None


def _merge_observation(cost: CostEvidence, observation: object | None) -> CostEvidence:
    if observation is None:
        return cost
    reported = _observation_decimal(getattr(observation, "reported_usd", None))
    estimated = _observation_decimal(getattr(observation, "estimated_usd", None))
    native = getattr(observation, "native_usage", None) or cost.native_usage
    snapshot = getattr(observation, "price_snapshot", None) or cost.price_snapshot
    if reported is not None:
        return CostEvidence(
            reported_usd=reported,
            source="reported",
            native_usage=native,
            price_snapshot=snapshot,
            line_items=[
                _line(
                    "reported_total",
                    Decimal(1),
                    "request",
                    reported,
                    "reported",
                    native=native,
                )
            ],
        )
    if estimated is not None:
        return CostEvidence(
            estimated_usd=estimated,
            source="estimated",
            native_usage=native,
            price_snapshot=snapshot,
            line_items=[
                _line(
                    "transport_estimate",
                    Decimal(1),
                    "request",
                    estimated,
                    "estimated",
                    native=native,
                )
            ],
        )
    if native is cost.native_usage and snapshot is cost.price_snapshot:
        return cost
    return CostEvidence(
        reported_usd=cost.reported_usd,
        estimated_usd=cost.estimated_usd,
        source=cost.source,
        native_usage=native,
        price_snapshot=snapshot,
        line_items=cost.line_items,
    )


def _usage_number(value: object) -> Decimal | None:
    number = _nonnegative_decimal(value)
    return number if number is not None else None
