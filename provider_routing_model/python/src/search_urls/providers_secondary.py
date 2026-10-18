"""Direct search adapters for Keenable, Parallel, Tinyfish, and You.com."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Literal, cast

from pydantic import JsonValue

from search_urls.configuration import SearchConfig
from search_urls.models import CostEvidence, SearchResponse
from search_urls.providers_secondary_support import (
    _ensure_search_payload,
    _line,
    _normalize_top_results,
    _options,
    _price_component,
    _price_rate,
    _price_snapshot,
    _provider_metadata,
    _raw_results,
    _response,
    _safe_metadata_value,
    _usage_number,
    _validate_pricing,
    _validate_wire_mode,
)
from search_urls.transport import SearchProviderError, SearchTransport

__all__ = ["KeenableAdapter", "ParallelAdapter", "TinyfishAdapter", "YouAdapter"]


class KeenableAdapter:
    """Keenable REST search with the keyless public endpoint when no key exists."""

    provider = "keenable"

    def __init__(self, config: SearchConfig, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        _validate_pricing(config)

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        options = _options(self.config)
        mode = options.get("mode", "pro")
        _validate_wire_mode(self.config, mode)
        if self.api_key is None and mode == "realtime":
            raise SearchProviderError(self.provider, "unsupported_mode")
        endpoint = "https://api.keenable.ai/v1/search"
        headers: dict[str, str]
        if self.api_key is None:
            endpoint += "/public"
            headers = {"X-Keenable-Title": "provider-evals"}
        else:
            headers = {"X-API-Key": self.api_key}
        body = {key: value for key, value in options.items() if key not in {"mode"}}
        body["query"] = query
        body["max_results"] = min(self.config.limit, 50)
        if mode is not None:
            body["mode"] = mode
        payload = await transport.request("POST", endpoint, headers=headers, json=body)
        _ensure_search_payload(self.provider, payload)
        raw_results = _raw_results(self.provider, payload)
        metadata = _provider_metadata(payload)
        results = _normalize_top_results(self.provider, raw_results, self.config.limit, metadata)
        cost = self._cost(payload, mode)
        return _response(self.config, query, payload, results, cost, metadata, len(raw_results))

    def _cost(self, payload: dict[str, object], mode: str) -> CostEvidence:
        usage = _keenable_usage(payload)
        actual_mode = _keenable_mode(usage, mode)
        if self.api_key is None and usage is None:
            rate: Decimal | None = Decimal(0)
            rate = _price_rate(self.config, self.provider, "request", rate)
            snapshot = _price_snapshot(
                self.config,
                self.provider,
                "keyless-free",
                [
                    _price_component(
                        "request",
                        "request",
                        rate,
                        "Archived LIMITS.md documents Keenable's keyless public tier as free",
                    )
                ],
            )
            return CostEvidence(
                estimated_usd=rate,
                source="estimated",
                price_snapshot=snapshot,
                line_items=[_line("request", Decimal(1), "request", rate, "estimated")],
            )
        if usage is not None and usage.get("paid") is False:
            quantity = usage.get("credits", usage.get("amount"))
            quantity_decimal = _usage_number(quantity)
            snapshot = _price_snapshot(
                self.config,
                self.provider,
                actual_mode,
                [
                    _price_component(
                        "reported_credit",
                        "credit",
                        Decimal(0),
                        "Keenable reported paid=false",
                    )
                ],
            )
            native = _native_keenable_usage(usage)
            return CostEvidence(
                reported_usd=Decimal(0),
                source="reported",
                native_usage=native,
                price_snapshot=snapshot,
                line_items=[
                    _line(
                        "credit",
                        quantity_decimal,
                        "credit",
                        Decimal(0),
                        "reported",
                        native=native,
                    )
                ],
            )

        rate = _price_rate(
            self.config,
            self.provider,
            "credit",
            _keenable_rate(actual_mode),
        )
        components = [_price_component("credit", "credit", rate, _keenable_basis(actual_mode))]
        snapshot = _price_snapshot(self.config, self.provider, actual_mode, components)
        quantity_raw = None if usage is None else usage.get("credits", usage.get("amount"))
        quantity = _usage_number(quantity_raw)
        if quantity is None and self.api_key is not None and rate is not None:
            quantity = Decimal(1)
        source: Literal["estimated", "unknown"] = (
            "estimated" if quantity is not None and rate is not None else "unknown"
        )
        estimated = quantity * rate if quantity is not None and rate is not None else None
        native = _native_keenable_usage(usage)
        line_rate = rate if source == "estimated" else None
        return CostEvidence(
            estimated_usd=estimated,
            source=source,
            native_usage=native,
            price_snapshot=snapshot,
            line_items=[_line("credit", quantity, "credit", line_rate, source, native=native)],
        )


def _as_json_object(value: dict[str, object] | None) -> JsonValue | None:
    if value is None:
        return None
    output: dict[str, JsonValue] = {}
    for key, item in value.items():
        safe = _safe_metadata_value(item)
        if safe is not None:
            output[key] = safe
    return output


def _native_keenable_usage(value: dict[str, object] | None) -> JsonValue | None:
    safe = _as_json_object(value)
    if safe is None:
        return None
    return {"keenable/usage": safe}


def _keenable_usage(payload: dict[str, object]) -> dict[str, object] | None:
    meta = payload.get("_meta")
    if meta is None:
        return None
    if not isinstance(meta, dict):
        raise SearchProviderError("keenable", "invalid_response", retryable=True)
    raw = meta.get("keenable/usage")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SearchProviderError("keenable", "invalid_response", retryable=True)
    usage: dict[str, object] = {}
    sku = raw.get("sku")
    if sku is not None:
        if not isinstance(sku, str) or not re.fullmatch(r"[\w][\w.:-]{0,99}", sku):
            raise SearchProviderError("keenable", "invalid_response", retryable=True)
        usage["sku"] = sku
    for key in ("amount", "credits"):
        if key in raw:
            quantity = _usage_number(raw[key])
            if quantity is None:
                raise SearchProviderError("keenable", "invalid_response", retryable=True)
            usage[key] = float(quantity)
    if "paid" in raw:
        if type(raw["paid"]) is not bool:
            raise SearchProviderError("keenable", "invalid_response", retryable=True)
        usage["paid"] = raw["paid"]
    if not usage:
        raise SearchProviderError("keenable", "invalid_response", retryable=True)
    return usage


def _keenable_mode(usage: dict[str, object] | None, fallback: str) -> str:
    sku = usage.get("sku") if usage is not None else None
    if not isinstance(sku, str):
        return fallback
    lowered = sku.casefold()
    for mode in ("realtime", "frontier", "cached", "live", "pro"):
        if mode in lowered:
            return mode
    return f"reported-sku:{lowered}"


def _keenable_rate(mode: str) -> Decimal | None:
    if mode in {"pro", "cached"}:
        return Decimal("0.004")
    if mode == "frontier":
        return Decimal("0.001")
    return None


def _keenable_basis(mode: str) -> str:
    if mode == "frontier":
        return "LIMITS.md reference: $1 per 1,000 Frontier requests"
    if mode in {"pro", "cached"}:
        return "LIMITS.md Agent Builder reference: $4 per 1,000; assumes one credit per request"
    return "No stable archived USD rate documented for this Keenable SKU"


class ParallelAdapter:
    """Parallel Search API adapter; result order and duplicates are preserved."""

    provider = "parallel"

    def __init__(self, config: SearchConfig, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = _require_key(self.provider, api_key)
        _validate_pricing(config)

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        options = _options(self.config)
        mode = options.get("mode", "advanced")
        _validate_wire_mode(self.config, mode)
        advanced = dict(options.get("advanced_settings", {}))
        requested_limit = advanced.get("max_results", self.config.limit)
        request_limit = min(self.config.limit, requested_limit, 20)
        advanced["max_results"] = request_limit
        body = {
            **{key: value for key, value in options.items() if key != "advanced_settings"},
            "objective": query,
            "search_queries": [query],
            "mode": mode,
            "advanced_settings": advanced,
        }
        payload = await transport.request(
            "POST",
            "https://api.parallel.ai/v1/search",
            headers={"x-api-key": self.api_key},
            json=body,
        )
        _ensure_search_payload(self.provider, payload)
        raw_results = _raw_results(self.provider, payload)
        metadata = _provider_metadata(payload)
        results = _normalize_top_results(self.provider, raw_results, request_limit, metadata)
        cost = _parallel_cost(self.config, payload, mode, len(raw_results))
        return _response(self.config, query, payload, results, cost, metadata, len(raw_results))


def _parallel_usage(payload: dict[str, object]) -> list[dict[str, JsonValue]] | None:
    raw = payload.get("usage")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise SearchProviderError("parallel", "invalid_response", retryable=True)
    usage: list[dict[str, JsonValue]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise SearchProviderError("parallel", "invalid_response", retryable=True)
        sku = item.get("sku", item.get("name"))
        count = _usage_number(item.get("count"))
        if not isinstance(sku, str) or not sku or count is None:
            raise SearchProviderError("parallel", "invalid_response", retryable=True)
        usage.append({"sku": sku[:100], "count": float(count)})
    return usage


def _parallel_cost(
    config: SearchConfig,
    payload: dict[str, object],
    mode: str,
    result_count: int,
) -> CostEvidence:
    usage = _parallel_usage(payload)
    unit_rate = _price_rate(
        config,
        "parallel",
        "request",
        Decimal("0.001") if mode in {"turbo", "fast"} else Decimal("0.005"),
    )
    extra_rate = _price_rate(config, "parallel", "extra_result", Decimal("0.001"))
    assert unit_rate is not None and extra_rate is not None
    extra_count = max(0, result_count - 10)
    components = [
        _price_component(
            "request",
            "request",
            unit_rate,
            f"Archived Parallel {mode} search request reference rate",
        ),
        _price_component("extra_result", "result", extra_rate, "$1 per 1,000 results above 10"),
    ]
    snapshot = _price_snapshot(config, "parallel", mode, components)
    native_usage: JsonValue | None = cast(JsonValue, usage) if usage is not None else None
    lines = [
        _line("request", Decimal(1), "request", unit_rate, "estimated"),
        _line("extra_result", Decimal(extra_count), "result", extra_rate, "estimated"),
    ]
    amount = unit_rate + Decimal(extra_count) * extra_rate
    return CostEvidence(
        estimated_usd=amount,
        source="estimated",
        native_usage=native_usage,
        price_snapshot=snapshot,
        line_items=lines,
    )


class TinyfishAdapter:
    """Tinyfish Search JSON endpoint; search does not use the browser-run SSE API."""

    provider = "tinyfish"

    def __init__(self, config: SearchConfig, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = _require_key(self.provider, api_key)
        _validate_pricing(config)

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        options = _options(self.config)
        _validate_tinyfish_options(options)
        params: dict[str, str | int | float | bool | None] = {"query": query, "page": 0}
        for key, value in options.items():
            if key in {"include_domains", "exclude_domains"}:
                if value:
                    params[key] = ",".join(value)
            else:
                params[key] = value
        payload = await transport.request(
            "GET",
            "https://api.search.tinyfish.ai",
            headers={"X-API-Key": self.api_key},
            params=params,
        )
        _ensure_search_payload(self.provider, payload)
        raw_results = _raw_results(self.provider, payload)
        metadata = _provider_metadata(payload)
        results = _normalize_top_results(self.provider, raw_results, self.config.limit, metadata)
        cost = _tinyfish_cost(self.config)
        return _response(self.config, query, payload, results, cost, metadata, len(raw_results))


def _validate_tinyfish_options(options: dict[str, Any]) -> None:
    if options.get("recency_minutes") is not None and (
        options.get("after_date") is not None or options.get("before_date") is not None
    ):
        raise SearchProviderError("tinyfish", "invalid_options")
    lower = options.get("pub_year_min")
    upper = options.get("pub_year_max")
    if lower is not None and upper is not None and lower > upper:
        raise SearchProviderError("tinyfish", "invalid_options")


def _tinyfish_cost(config: SearchConfig) -> CostEvidence:
    rate = _price_rate(config, "tinyfish", "request", Decimal(0))
    basis = "Archived FreeSearch LIMITS.md lists Tinyfish Search as no wallet charge"
    snapshot = _price_snapshot(
        config,
        "tinyfish",
        "free",
        [_price_component("request", "request", rate, basis)],
    )
    assert rate is not None
    return CostEvidence(
        estimated_usd=rate,
        source="estimated",
        price_snapshot=snapshot,
        line_items=[_line("request", Decimal(1), "request", rate, "estimated")],
    )


class YouAdapter:
    """You.com YDC Index Web Search API adapter."""

    provider = "you"

    def __init__(self, config: SearchConfig, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = _require_key(self.provider, api_key)
        _validate_pricing(config)

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        options = _options(self.config)
        _validate_you_options(options)
        body = dict(options)
        extraction = body.pop("extraction", None)
        if isinstance(extraction, dict):
            wire_extraction: dict[str, Any] = {
                "extraction_mode": extraction["mode"],
            }
            if "source" in extraction:
                wire_extraction["extraction_source"] = extraction["source"]
            if "highlights" in extraction:
                wire_extraction["highlights"] = extraction["highlights"]
            if "full_page" in extraction:
                wire_extraction["full_page"] = extraction["full_page"]
            body["extraction"] = wire_extraction
        body["query"] = query
        body["count"] = self.config.limit
        payload = await transport.request(
            "POST",
            "https://ydc-index.io/v1/search",
            headers={"X-API-Key": self.api_key},
            json=body,
        )
        _ensure_search_payload(self.provider, payload)
        raw_results = _raw_results(self.provider, payload)
        metadata = _provider_metadata(payload)
        results = _normalize_top_results(self.provider, raw_results, self.config.limit, metadata)
        cost = _you_cost(self.config, options, len(raw_results))
        return _response(self.config, query, payload, results, cost, metadata, len(raw_results))


def _validate_you_options(options: dict[str, Any]) -> None:
    include = options.get("include_domains")
    exclude = options.get("exclude_domains")
    boost = options.get("boost_domains")
    if (include and exclude) or (include and boost):
        raise SearchProviderError("you", "invalid_options")
    country = options.get("country")
    if country is not None and len(country) != 2:
        raise SearchProviderError("you", "invalid_options")
    language = options.get("language")
    if language is not None and not 2 <= len(language) <= 16:
        raise SearchProviderError("you", "invalid_options")
    extraction = options.get("extraction")
    if isinstance(extraction, dict):
        mode = extraction.get("mode")
        if mode == "highlights" and extraction.get("full_page") is not None:
            raise SearchProviderError("you", "invalid_options")
        if mode == "full_page" and extraction.get("highlights") is not None:
            raise SearchProviderError("you", "invalid_options")


def _you_cost(config: SearchConfig, options: dict[str, Any], result_count: int) -> CostEvidence:
    base_rate = _price_rate(config, "you", "request", Decimal("0.005"))
    assert base_rate is not None
    extraction = options.get("extraction")
    extraction_mode = extraction.get("mode") if isinstance(extraction, dict) else None
    source = extraction.get("source") if isinstance(extraction, dict) else None
    live_pages = extraction_mode == "full_page" and source != "cache"
    page_rate = _price_rate(config, "you", "live_page", Decimal("0.001"))
    assert page_rate is not None
    components = [
        _price_component(
            "request",
            "request",
            base_rate,
            "$5 per 1,000 Web Search calls; first 100 daily calls may be free",
        )
    ]
    lines = [_line("request", Decimal(1), "request", base_rate, "estimated")]
    amount: Decimal | None = base_rate
    if live_pages:
        components.append(
            _price_component("live_page", "page", page_rate, "$1 per 1,000 live extraction pages")
        )
        if source == "fetch":
            lines.append(_line("live_page", Decimal(result_count), "page", page_rate, "estimated"))
            if amount is not None:
                amount += Decimal(result_count) * page_rate
        elif source == "cache":
            lines.append(_line("live_page", Decimal(0), "page", page_rate, "estimated"))
        else:
            lines.append(_line("live_page", None, "page", None, "unknown"))
            amount = None
    snapshot = _price_snapshot(
        config,
        "you",
        "search+full_page" if live_pages else "search",
        components,
    )
    return CostEvidence(
        estimated_usd=amount,
        source="estimated" if amount is not None else "unknown",
        price_snapshot=snapshot,
        line_items=lines,
    )


def _require_key(provider: str, api_key: str | None) -> str:
    key = api_key.strip() if isinstance(api_key, str) else ""
    if not key:
        raise SearchProviderError(provider, "configuration_error")
    return key
