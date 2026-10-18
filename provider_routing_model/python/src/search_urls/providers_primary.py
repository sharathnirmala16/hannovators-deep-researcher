"""Primary search provider adapters for Exa, Tavily, Brave, and Firecrawl."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from pydantic import JsonValue

from search_urls.configuration import SearchConfig
from search_urls.models import (
    CostEvidence,
    CostLineItem,
    ProviderName,
    SearchResponse,
    SearchResult,
    _safe_url,
)
from search_urls.provider_helpers import (
    BRAVE_ALLOWED_OPTIONS,
    BRAVE_COST_PER_REQUEST,
    BRAVE_LOCATION_HEADERS,
    BRAVE_NON_QUERY_OPTIONS,
    BRAVE_SEARCH_URL,
    EXA_ALLOWED_OPTIONS,
    EXA_BASE_RATES,
    EXA_CAMEL_KEYS,
    EXA_SEARCH_URL,
    EXA_VALID_TYPES,
    FIRECRAWL_ALLOWED_OPTIONS,
    FIRECRAWL_CREDIT_RATE,
    FIRECRAWL_SEARCH_URL,
    TAVILY_ALLOWED_OPTIONS,
    TAVILY_CREDIT_USD,
    TAVILY_SEARCH_URL,
    TAVILY_VALID_DEPTHS,
    TAVILY_VALID_TOPICS,
    build_price_snapshot,
    check_payload_status,
    clean_str,
    extract_scores,
    firecrawl_wire,
    to_finite_float,
    validate_provider_pricing,
)
from search_urls.transport import SearchProviderError, SearchTransport


class ProviderAdapter(ABC):
    """Abstract direct search provider adapter."""

    name: ProviderName

    def __init__(self, config: SearchConfig, key: str | None = None) -> None:
        clean_options = {key: value for key, value in config.options.items() if value is not None}
        self.config = config.model_copy(update={"options": clean_options})
        self.key = key.strip() if isinstance(key, str) and key.strip() else None
        validate_provider_pricing(self.name, config.pricing, self.key)

    @abstractmethod
    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        """Execute a normalized search query via the shared transport."""
        raise NotImplementedError


# ============================================================================
# Exa Adapter
# ============================================================================


class ExaAdapter(ProviderAdapter):
    """Exa Neural Search API adapter."""

    name: ProviderName = "exa"

    def __init__(self, config: SearchConfig, key: str | None = None) -> None:
        super().__init__(config, key)
        if not self.key:
            raise SearchProviderError(self.name, "configuration_error", retryable=False)
        self._validate_options()

    def _validate_options(self) -> None:
        unknown = set(self.config.options.keys()) - EXA_ALLOWED_OPTIONS
        if unknown:
            raise SearchProviderError(self.name, "bad_request", retryable=False)
        req_type = self.config.options.get("type")
        if req_type is not None and req_type not in EXA_VALID_TYPES:
            raise SearchProviderError(self.name, "bad_request", retryable=False)
        contents = self.config.options.get("contents")
        if contents is not None and not isinstance(contents, dict):
            raise SearchProviderError(self.name, "bad_request", retryable=False)

    @staticmethod
    def _extract_snippet(raw: dict[str, Any]) -> str:
        highlights = raw.get("highlights")
        if isinstance(highlights, list) and highlights:
            first_hl = next((h for h in highlights if isinstance(h, str) and h.strip()), None)
            if first_hl:
                return first_hl
        text_val = raw.get("text")
        if isinstance(text_val, str) and text_val:
            return text_val
        summary_val = raw.get("summary")
        if isinstance(summary_val, str) and summary_val:
            return str(summary_val)
        return ""

    @staticmethod
    def _extract_metadata(raw: dict[str, Any]) -> dict[str, JsonValue]:
        item_metadata: dict[str, JsonValue] = {}
        if "id" in raw and isinstance(raw["id"], (str, int)):
            item_metadata["id"] = raw["id"]
        if "favicon" in raw and isinstance(raw["favicon"], str):
            item_metadata["favicon"] = raw["favicon"]
        if "image" in raw and isinstance(raw["image"], str):
            item_metadata["image"] = raw["image"]
        for field in (
            "highlights",
            "highlight_scores",
            "highlightScores",
            "crawl_date",
            "crawlDate",
            "subpages",
            "extras",
            "entities",
        ):
            if field in raw:
                item_metadata[field] = raw[field]
        return item_metadata

    def _parse_results(self, raw_results: list[object]) -> tuple[list[SearchResult], int]:
        results: list[SearchResult] = []
        summary_count = 0
        for provider_idx, raw in enumerate(raw_results):
            if not isinstance(raw, dict):
                continue
            raw_url = raw.get("url")
            if not isinstance(raw_url, str) or not raw_url:
                continue
            try:
                safe_url = _safe_url(raw_url)
            except ValueError:
                continue

            title = str(raw.get("title") or "")
            snippet = self._extract_snippet(raw)
            content = raw.get("text") if isinstance(raw.get("text"), str) else None
            summary = raw.get("summary") if isinstance(raw.get("summary"), str) else None
            if summary:
                summary_count += 1
            markdown = raw.get("markdown") if isinstance(raw.get("markdown"), str) else None
            author = raw.get("author") if isinstance(raw.get("author"), str) else None
            published_at = clean_str(raw.get("publishedDate") or raw.get("published_date"))
            score_val, scores = extract_scores(raw)
            item_metadata = self._extract_metadata(raw)

            res_rank = len(results) + 1
            results.append(
                SearchResult(
                    rank=res_rank,
                    provider_rank=provider_idx + 1,
                    title=title,
                    url=safe_url,
                    snippet=snippet,
                    content=content,
                    summary=summary,
                    markdown=markdown,
                    author=author,
                    published_at=published_at,
                    score=score_val,
                    scores=scores,
                    metadata=item_metadata,
                )
            )
            if len(results) >= self.config.limit:
                break
        return results, summary_count

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        assert self.key is not None
        headers = {
            "x-api-key": self.key,
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {}
        for opt_key, opt_val in self.config.options.items():
            if opt_key == "contents":
                continue
            wire_key = EXA_CAMEL_KEYS.get(opt_key, opt_key)
            body[wire_key] = opt_val

        body["query"] = query
        body["numResults"] = self.config.limit

        contents_opt = self.config.options.get("contents")
        if isinstance(contents_opt, dict):
            body["contents"] = {
                "highlights": True,
                **{EXA_CAMEL_KEYS.get(k, k): v for k, v in contents_opt.items()},
            }
        else:
            body["contents"] = {"highlights": True}

        raw_payload = await transport.request("POST", EXA_SEARCH_URL, headers=headers, json=body)
        payload = check_payload_status(self.name, raw_payload)

        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise SearchProviderError(
                self.name, "invalid_response", status_code=200, retryable=True
            )

        results, summary_count = self._parse_results(raw_results)
        if len(raw_results) > 0 and len(results) == 0:
            raise SearchProviderError(
                self.name, "invalid_response", status_code=200, retryable=True
            )

        # Latency (explicit None selection so valid 0 is not lost)
        raw_latency = payload.get("searchTime")
        if raw_latency is None:
            raw_latency = payload.get("search_time")

        latency_ms: float | None = None
        if raw_latency is not None:
            parsed_lat = to_finite_float(raw_latency)
            if parsed_lat is not None and parsed_lat >= 0:
                latency_ms = parsed_lat

        request_id = clean_str(payload.get("requestId") or payload.get("request_id"))
        cost_evidence = self._calculate_cost(payload, len(raw_results), summary_count)

        provider_metadata: dict[str, JsonValue] = {}
        if latency_ms is not None:
            provider_metadata["provider_reported_latency_ms"] = latency_ms
        if request_id is not None:
            provider_metadata["provider_request_id"] = request_id

        return SearchResponse(
            query=query,
            provider=self.name,
            results=results,
            total_results=len(results),
            provider_reported_latency_ms=latency_ms,
            provider_request_id=request_id,
            cost=cost_evidence,
            provider_metadata=provider_metadata,
        )

    def _calculate_cost(
        self, payload: dict[str, Any], raw_result_count: int, summary_count: int
    ) -> CostEvidence:
        cost_dollars = payload.get("costDollars")
        if isinstance(cost_dollars, dict) and "total" in cost_dollars:
            total_num = to_finite_float(cost_dollars["total"])
            if total_num is not None and total_num >= 0:
                reported_usd = Decimal(str(total_num))
                line_item = CostLineItem(
                    name="exa_search",
                    quantity=Decimal("1"),
                    unit="request",
                    unit_price_usd=reported_usd,
                    total_usd=reported_usd,
                    source="reported",
                    native=cost_dollars,
                )
                return CostEvidence(
                    reported_usd=reported_usd,
                    source="reported",
                    native_usage=cost_dollars,
                    line_items=[line_item],
                )

        req_type = str(self.config.options.get("type", "auto"))
        default_rate = EXA_BASE_RATES.get(req_type, Decimal("0.007"))
        if self.config.pricing and req_type in self.config.pricing.rates:
            base_rate = Decimal(str(self.config.pricing.rates[req_type]))
        elif self.config.pricing and self.config.pricing.rate_per_request is not None:
            base_rate = self.config.pricing.rate_per_request
        else:
            base_rate = default_rate

        line_items: list[CostLineItem] = [
            CostLineItem(
                name=f"exa_{req_type}_search",
                quantity=Decimal("1"),
                unit="request",
                unit_price_usd=base_rate,
                total_usd=base_rate,
                source="estimated",
            )
        ]

        extra_results = max(0, raw_result_count - 10)
        extra_cost = Decimal(extra_results) * Decimal("0.001")
        if extra_results > 0:
            line_items.append(
                CostLineItem(
                    name="exa_extra_result",
                    quantity=Decimal(extra_results),
                    unit="result",
                    unit_price_usd=Decimal("0.001"),
                    total_usd=extra_cost,
                    source="estimated",
                )
            )

        summary_cost = Decimal(summary_count) * Decimal("0.001")
        if summary_count > 0:
            line_items.append(
                CostLineItem(
                    name="exa_summary",
                    quantity=Decimal(summary_count),
                    unit="summary",
                    unit_price_usd=Decimal("0.001"),
                    total_usd=summary_cost,
                    source="estimated",
                )
            )

        estimated_usd = base_rate + extra_cost + summary_cost
        snapshot = build_price_snapshot(
            self.name,
            self.config.pricing,
            default_plan="paygo-reference",
            wire_mode="keyed",
            extra={"type": req_type, "base_rate_usd": str(base_rate)},
        )
        return CostEvidence(
            estimated_usd=estimated_usd,
            source="estimated",
            price_snapshot=snapshot,
            line_items=line_items,
        )


# ============================================================================
# Tavily Adapter
# ============================================================================


class TavilyAdapter(ProviderAdapter):
    """Tavily Search API adapter supporting keyed and keyless modes."""

    name: ProviderName = "tavily"

    def __init__(self, config: SearchConfig, key: str | None = None) -> None:
        super().__init__(config, key)
        self._validate_options()

    def _validate_options(self) -> None:
        unknown = set(self.config.options.keys()) - TAVILY_ALLOWED_OPTIONS
        if unknown:
            raise SearchProviderError(self.name, "bad_request", retryable=False)
        depth = self.config.options.get("search_depth")
        if depth is not None and depth not in TAVILY_VALID_DEPTHS:
            raise SearchProviderError(self.name, "bad_request", retryable=False)
        topic = self.config.options.get("topic")
        if topic is not None and topic not in TAVILY_VALID_TOPICS:
            raise SearchProviderError(self.name, "bad_request", retryable=False)

    def _parse_results(self, raw_results: list[object]) -> list[SearchResult]:
        results: list[SearchResult] = []
        for provider_idx, raw in enumerate(raw_results):
            if not isinstance(raw, dict):
                continue
            raw_url = raw.get("url")
            if not isinstance(raw_url, str) or not raw_url:
                continue
            try:
                safe_url = _safe_url(raw_url)
            except ValueError:
                continue

            title = str(raw.get("title") or "")
            snippet = str(raw.get("content") or "")
            content = raw.get("raw_content") if isinstance(raw.get("raw_content"), str) else None
            published_at = clean_str(raw.get("published_date"))
            markdown = raw.get("markdown") if isinstance(raw.get("markdown"), str) else None
            summary = raw.get("summary") if isinstance(raw.get("summary"), str) else None

            score_val, scores = extract_scores(raw)

            item_metadata: dict[str, JsonValue] = {}
            if "favicon" in raw and isinstance(raw["favicon"], str):
                item_metadata["favicon"] = raw["favicon"]
            if "images" in raw and isinstance(raw["images"], list):
                item_metadata["images"] = [img for img in raw["images"] if isinstance(img, str)]

            res_rank = len(results) + 1
            results.append(
                SearchResult(
                    rank=res_rank,
                    provider_rank=provider_idx + 1,
                    title=title,
                    url=safe_url,
                    snippet=snippet,
                    content=content,
                    summary=summary,
                    markdown=markdown,
                    author=None,
                    published_at=published_at,
                    score=score_val,
                    scores=scores,
                    metadata=item_metadata,
                )
            )
            if len(results) >= self.config.limit:
                break
        return results

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        else:
            headers["X-Tavily-Access-Mode"] = "keyless"

        body: dict[str, Any] = dict(self.config.options)
        depth = str(body.get("search_depth", "basic"))

        # Pin parameters
        body["query"] = query
        body["max_results"] = min(self.config.limit, 20)
        body["search_depth"] = depth
        body["include_usage"] = True

        raw_payload = await transport.request("POST", TAVILY_SEARCH_URL, headers=headers, json=body)
        payload = check_payload_status(self.name, raw_payload)

        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise SearchProviderError(
                self.name, "invalid_response", status_code=200, retryable=True
            )

        results = self._parse_results(raw_results)
        if len(raw_results) > 0 and len(results) == 0:
            raise SearchProviderError(
                self.name, "invalid_response", status_code=200, retryable=True
            )

        # Latency: response_time can be seconds as number or numeric string
        raw_latency = payload.get("response_time")
        latency_ms: float | None = None
        if raw_latency is not None:
            latency_sec = to_finite_float(raw_latency)
            if latency_sec is not None and latency_sec >= 0:
                val_ms = latency_sec * 1000.0
                if math.isfinite(val_ms):
                    latency_ms = val_ms

        request_id = clean_str(payload.get("request_id") or payload.get("requestId"))
        cost_evidence = self._calculate_cost(payload, depth)

        provider_metadata: dict[str, JsonValue] = {}
        if latency_ms is not None:
            provider_metadata["provider_reported_latency_ms"] = latency_ms
        if request_id is not None:
            provider_metadata["provider_request_id"] = request_id

        return SearchResponse(
            query=query,
            provider=self.name,
            results=results,
            total_results=len(results),
            provider_reported_latency_ms=latency_ms,
            provider_request_id=request_id,
            cost=cost_evidence,
            provider_metadata=provider_metadata,
        )

    def _calculate_cost(self, payload: dict[str, Any], depth: str) -> CostEvidence:
        raw_usage = payload.get("usage")
        reported_credits: Decimal | None = None
        if isinstance(raw_usage, dict) and "credits" in raw_usage:
            credits_num = to_finite_float(raw_usage["credits"])
            if credits_num is not None and credits_num >= 0:
                reported_credits = Decimal(str(credits_num))

        is_keyless = self.key is None
        wire_mode = "keyless" if is_keyless else "keyed"
        default_plan = "keyless-free" if is_keyless else "paygo-reference"

        # Explicit valid 0 preservation
        if is_keyless:
            unit_price = Decimal("0")
        elif self.config.pricing and self.config.pricing.usd_per_credit is not None:
            unit_price = self.config.pricing.usd_per_credit
        else:
            unit_price = TAVILY_CREDIT_USD

        snapshot = build_price_snapshot(
            self.name,
            self.config.pricing,
            default_plan=default_plan,
            wire_mode=wire_mode,
            extra={"usd_per_credit": str(unit_price)},
        )

        if reported_credits is not None:
            total_usd = reported_credits * unit_price
            line_item = CostLineItem(
                name="tavily_credits",
                quantity=reported_credits,
                unit="credit",
                unit_price_usd=unit_price,
                total_usd=total_usd,
                source="estimated",
                native=raw_usage,
            )
            return CostEvidence(
                estimated_usd=total_usd,
                source="estimated",
                native_usage=raw_usage,
                price_snapshot=snapshot,
                line_items=[line_item],
            )

        credits_est = Decimal("2") if depth == "advanced" else Decimal("1")
        total_usd = credits_est * unit_price
        line_item = CostLineItem(
            name="tavily_credits",
            quantity=credits_est,
            unit="credit",
            unit_price_usd=unit_price,
            total_usd=total_usd,
            source="estimated",
        )
        return CostEvidence(
            estimated_usd=total_usd,
            source="estimated",
            price_snapshot=snapshot,
            line_items=[line_item],
        )


# ============================================================================
# Brave Adapter
# ============================================================================


class BraveAdapter(ProviderAdapter):
    """Brave Web Search API adapter (search only; answers not ordered search; no fetch)."""

    name: ProviderName = "brave"

    def __init__(self, config: SearchConfig, key: str | None = None) -> None:
        super().__init__(config, key)
        if not self.key:
            raise SearchProviderError(self.name, "configuration_error", retryable=False)
        self._validate_options()

    def _validate_options(self) -> None:
        unknown = set(self.config.options.keys()) - BRAVE_ALLOWED_OPTIONS
        if unknown:
            raise SearchProviderError(self.name, "bad_request", retryable=False)

    def _parse_results(self, raw_results: list[object]) -> list[SearchResult]:
        results: list[SearchResult] = []
        for provider_idx, raw in enumerate(raw_results):
            if not isinstance(raw, dict):
                continue
            raw_url = raw.get("url")
            if not isinstance(raw_url, str) or not raw_url:
                continue
            try:
                safe_url = _safe_url(raw_url)
            except ValueError:
                continue

            title = str(raw.get("title") or "")
            snippet = str(raw.get("description") or "")
            published_at = clean_str(raw.get("page_age"))
            markdown = raw.get("markdown") if isinstance(raw.get("markdown"), str) else None
            summary = raw.get("summary") if isinstance(raw.get("summary"), str) else None

            score_val, scores = extract_scores(raw)

            item_metadata: dict[str, JsonValue] = {}
            for meta_k in ("language", "subtype", "age", "family_friendly"):
                if meta_k in raw and raw[meta_k] is not None:
                    item_metadata[meta_k] = raw[meta_k]

            res_rank = len(results) + 1
            results.append(
                SearchResult(
                    rank=res_rank,
                    provider_rank=provider_idx + 1,
                    title=title,
                    url=safe_url,
                    snippet=snippet,
                    content=None,
                    summary=summary,
                    markdown=markdown,
                    author=None,
                    published_at=published_at,
                    score=score_val,
                    scores=scores,
                    metadata=item_metadata,
                )
            )
            if len(results) >= self.config.limit:
                break
        return results

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        assert self.key is not None
        headers: dict[str, str] = {"X-Subscription-Token": self.key}

        options = self.config.options
        if options.get("no_cache"):
            headers["Cache-Control"] = "no-cache"
        api_ver = options.get("api_version")
        if isinstance(api_ver, str):
            headers["Api-Version"] = api_ver

        loc = options.get("location")
        if isinstance(loc, dict):
            for field, hdr in BRAVE_LOCATION_HEADERS.items():
                val = loc.get(field)
                if val is not None:
                    headers[hdr] = str(val)

        params: dict[str, str | int | float | bool | None] = {}
        for k, v in options.items():
            if k in BRAVE_ALLOWED_OPTIONS and v is not None and k not in BRAVE_NON_QUERY_OPTIONS:
                if k == "result_filter" and isinstance(v, list):
                    params[k] = ",".join(str(item) for item in v)
                elif isinstance(v, (str, int, float, bool)):
                    params[k] = v

        params["q"] = query
        params["count"] = min(self.config.limit, 20)

        raw_payload = await transport.request(
            "GET", BRAVE_SEARCH_URL, headers=headers, params=params
        )
        payload = check_payload_status(self.name, raw_payload)

        web = payload.get("web")
        # Brave omits `web` for a valid search with zero web results.
        if (
            web is None
            and payload.get("type") == "search"
            and isinstance(payload.get("query"), dict)
        ):
            web = {"results": []}
        if not isinstance(web, dict):
            raise SearchProviderError(
                self.name, "invalid_response", status_code=200, retryable=True
            )

        raw_results = web.get("results")
        if not isinstance(raw_results, list):
            raise SearchProviderError(
                self.name, "invalid_response", status_code=200, retryable=True
            )

        results = self._parse_results(raw_results)
        if len(raw_results) > 0 and len(results) == 0:
            raise SearchProviderError(
                self.name, "invalid_response", status_code=200, retryable=True
            )

        rate = (
            self.config.pricing.rate_per_request
            if self.config.pricing and self.config.pricing.rate_per_request is not None
            else BRAVE_COST_PER_REQUEST
        )
        line_item = CostLineItem(
            name="brave_search",
            quantity=Decimal("1"),
            unit="request",
            unit_price_usd=rate,
            total_usd=rate,
            source="estimated",
        )
        snapshot = build_price_snapshot(
            self.name,
            self.config.pricing,
            default_plan="web-reference",
            wire_mode="keyed",
            extra={"cost_per_request_usd": str(rate)},
        )
        cost_evidence = CostEvidence(
            estimated_usd=rate,
            source="estimated",
            price_snapshot=snapshot,
            line_items=[line_item],
        )

        return SearchResponse(
            query=query,
            provider=self.name,
            results=results,
            total_results=len(results),
            provider_reported_latency_ms=None,
            provider_request_id=None,
            cost=cost_evidence,
            provider_metadata={},
        )


# ============================================================================
# Firecrawl Adapter
# ============================================================================


class FirecrawlAdapter(ProviderAdapter):
    """Firecrawl Search API adapter."""

    name: ProviderName = "firecrawl"

    def __init__(self, config: SearchConfig, key: str | None = None) -> None:
        super().__init__(config, key)
        if not self.key:
            raise SearchProviderError(self.name, "configuration_error", retryable=False)
        self._validate_options()

    def _validate_options(self) -> None:
        unknown = set(self.config.options.keys()) - FIRECRAWL_ALLOWED_OPTIONS
        if unknown:
            raise SearchProviderError(self.name, "bad_request", retryable=False)
        scrape = self.config.options.get("scrape_options")
        if scrape is not None:
            allowed_scrape = {
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
                "timeout",
            }
            if not isinstance(scrape, dict) or set(scrape) - allowed_scrape:
                raise SearchProviderError(self.name, "bad_request", retryable=False)

    def _parse_items(self, raw_items: list[tuple[str, dict[str, Any]]]) -> list[SearchResult]:
        results: list[SearchResult] = []
        for provider_idx, (source, item) in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            raw_meta = item.get("metadata")
            page_meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
            raw_url = item.get("url") or page_meta.get("url")
            if not raw_url and source == "images":
                raw_url = item.get("image_url")
            if not isinstance(raw_url, str) or not raw_url:
                continue
            try:
                safe_url = _safe_url(raw_url)
            except ValueError:
                continue

            title = str(item.get("title") or page_meta.get("title") or "")
            snippet = str(
                item.get("description")
                or item.get("snippet")
                or item.get("summary")
                or item.get("markdown")
                or ""
            )
            markdown = item.get("markdown") if isinstance(item.get("markdown"), str) else None
            summary = item.get("summary") if isinstance(item.get("summary"), str) else None
            content = item.get("content") if isinstance(item.get("content"), str) else None
            author = clean_str(page_meta.get("author") or item.get("author"))
            published_at = clean_str(
                item.get("date") or item.get("published_date") or page_meta.get("published_time")
            )

            score_val, scores = extract_scores(item)

            item_metadata: dict[str, JsonValue] = {"source": source}
            status_code = page_meta.get("statusCode")
            if isinstance(status_code, int):
                item_metadata["status_code"] = status_code
            for k in ("language", "country"):
                val = page_meta.get(k)
                if isinstance(val, (str, int, float, bool)):
                    item_metadata[k] = val

            res_rank = len(results) + 1
            results.append(
                SearchResult(
                    rank=res_rank,
                    provider_rank=provider_idx + 1,
                    title=title,
                    url=safe_url,
                    snippet=snippet,
                    content=content,
                    summary=summary,
                    markdown=markdown,
                    author=author,
                    published_at=published_at,
                    score=score_val,
                    scores=scores,
                    metadata=item_metadata,
                )
            )
            if len(results) >= self.config.limit:
                break
        return results

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        assert self.key is not None
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {}
        wire_opts = firecrawl_wire(self.config.options)
        if isinstance(wire_opts, dict):
            body.update(wire_opts)

        body["query"] = query
        body["limit"] = self.config.limit

        raw_payload = await transport.request(
            "POST", FIRECRAWL_SEARCH_URL, headers=headers, json=body
        )
        payload = check_payload_status(self.name, raw_payload)

        data = payload.get("data")
        if data is None:
            data = payload

        raw_items: list[tuple[str, dict[str, Any]]] = []
        if isinstance(data, list):
            raw_items = [("web", it) for it in data if isinstance(it, dict)]
        elif isinstance(data, dict):
            has_channels = False
            for source in ("web", "news", "images"):
                channel_list = data.get(source)
                if channel_list is not None:
                    has_channels = True
                    if isinstance(channel_list, list):
                        raw_items.extend(
                            (source, it) for it in channel_list if isinstance(it, dict)
                        )
            if not has_channels and not any(k in data for k in ("research", "tools")):
                raise SearchProviderError(
                    self.name, "invalid_response", status_code=200, retryable=True
                )
        else:
            raise SearchProviderError(
                self.name, "invalid_response", status_code=200, retryable=True
            )

        results = self._parse_items(raw_items)
        if len(raw_items) > 0 and len(results) == 0:
            raise SearchProviderError(
                self.name, "invalid_response", status_code=200, retryable=True
            )

        request_id = clean_str(
            payload.get("requestId") or payload.get("request_id") or payload.get("id")
        )
        cost_evidence = self._calculate_cost(payload, len(results))

        provider_metadata: dict[str, JsonValue] = {}
        if request_id is not None:
            provider_metadata["provider_request_id"] = request_id

        return SearchResponse(
            query=query,
            provider=self.name,
            results=results,
            total_results=len(results),
            provider_reported_latency_ms=None,
            provider_request_id=request_id,
            cost=cost_evidence,
            provider_metadata=provider_metadata,
        )

    def _calculate_cost(self, payload: dict[str, Any], result_count: int) -> CostEvidence:
        raw_usage = payload.get("usage")
        reported_credits: Decimal | None = None
        raw_credits = None
        if isinstance(raw_usage, dict) and "credits" in raw_usage:
            raw_credits = raw_usage["credits"]
        elif "creditsUsed" in payload:
            raw_credits = payload["creditsUsed"]
        elif "credits_used" in payload:
            raw_credits = payload["credits_used"]

        credits_num = to_finite_float(raw_credits)
        if credits_num is not None and credits_num >= 0:
            reported_credits = Decimal(str(credits_num))

        rate = (
            self.config.pricing.usd_per_credit
            if self.config.pricing and self.config.pricing.usd_per_credit is not None
            else FIRECRAWL_CREDIT_RATE
        )
        snapshot = build_price_snapshot(
            self.name,
            self.config.pricing,
            default_plan="hobby-reference",
            wire_mode="keyed",
            extra={"usd_per_credit": str(rate)},
        )

        if reported_credits is not None:
            total_usd = reported_credits * rate
            native_dict: dict[str, JsonValue] = {"credits": float(reported_credits)}
            line_item = CostLineItem(
                name="firecrawl_credits",
                quantity=reported_credits,
                unit="credit",
                unit_price_usd=rate,
                total_usd=total_usd,
                source="estimated",
                native=native_dict,
            )
            return CostEvidence(
                estimated_usd=total_usd,
                source="estimated",
                native_usage=native_dict,
                price_snapshot=snapshot,
                line_items=[line_item],
            )

        est_credits = Decimal("2")
        total_usd = est_credits * rate
        line_item = CostLineItem(
            name="firecrawl_search",
            quantity=est_credits,
            unit="credit",
            unit_price_usd=rate,
            total_usd=total_usd,
            source="estimated",
        )
        return CostEvidence(
            estimated_usd=total_usd,
            source="estimated",
            price_snapshot=snapshot,
            line_items=[line_item],
        )


__all__ = [
    "BraveAdapter",
    "ExaAdapter",
    "FirecrawlAdapter",
    "ProviderAdapter",
    "TavilyAdapter",
]
