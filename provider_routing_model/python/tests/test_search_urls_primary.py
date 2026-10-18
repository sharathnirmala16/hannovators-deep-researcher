"""Focused offline tests for primary search provider adapters (Exa, Tavily, Brave, Firecrawl)."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from search_urls.configuration import SearchConfig
from search_urls.models import SearchResponse
from search_urls.providers_primary import (
    BraveAdapter,
    ExaAdapter,
    FirecrawlAdapter,
    ProviderAdapter,
    TavilyAdapter,
)
from search_urls.transport import SearchProviderError, SearchTransport


class DummyTransport:
    """Mock implementation of SearchTransport returning fixed responses."""

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.recorded_requests: list[dict[str, Any]] = []
        self.attempt_ids: list[str] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        json: Any = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        self.recorded_requests.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "params": dict(params or {}),
                "json": json,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response

    def for_query(
        self,
        case_id: str,
        repetition: int,
        retry: int,
        request_cap: int,
        deadline: float | None = None,
        initial_request_count: int = 0,
    ) -> SearchTransport:
        return self

    def finish_query(self, status: str, error_code: str | None = None) -> None:
        pass


def make_config(
    provider: str,
    *,
    limit: int = 5,
    options: dict[str, Any] | None = None,
    pricing: dict[str, Any] | None = None,
) -> SearchConfig:
    return SearchConfig.model_validate(
        {
            "schemaVersion": "search-collection-config/v1",
            "provider": provider,
            "limit": limit,
            "options": options or {},
            "pricing": pricing,
            "rateLimits": [{"requests": 1, "windowMs": 1000}],
            "limits": {
                "requestTimeoutMs": 10000,
                "queryTimeoutMs": 30000,
                "maxRequestsPerQuery": 5,
                "maxRetries": 1,
            },
        }
    )


class TestPrimaryAdapters(unittest.IsolatedAsyncioTestCase):
    def test_negative_pricing_override_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            make_config("brave", pricing={"rate_per_request": "-0.01"})

    def test_unsupported_pricing_fields_rejected(self) -> None:
        # Tavily rejects rate_per_request
        cfg1 = make_config("tavily", pricing={"rate_per_request": "0.01"})
        with self.assertRaises(SearchProviderError) as ctx:
            TavilyAdapter(cfg1, key="key")
        self.assertEqual(ctx.exception.code, "configuration_error")

        # Brave rejects usd_per_credit
        cfg2 = make_config("brave", pricing={"usd_per_credit": "0.01"})
        with self.assertRaises(SearchProviderError) as ctx:
            BraveAdapter(cfg2, key="key")
        self.assertEqual(ctx.exception.code, "configuration_error")

        # Exa rejects unknown type in rates map
        cfg3 = make_config("exa", pricing={"rates": {"unknown_type": "0.01"}})
        with self.assertRaises(SearchProviderError) as ctx:
            ExaAdapter(cfg3, key="key")
        self.assertEqual(ctx.exception.code, "configuration_error")

    def test_tavily_conflicting_mode_rejected(self) -> None:
        # Keyless mode configured, but key provided
        cfg = make_config("tavily", pricing={"mode": "keyless"})
        with self.assertRaises(SearchProviderError) as ctx:
            TavilyAdapter(cfg, key="actual-secret-key")
        self.assertEqual(ctx.exception.code, "configuration_error")

        # Keyed mode configured, but no key provided
        cfg2 = make_config("tavily", pricing={"mode": "paygo"})
        with self.assertRaises(SearchProviderError) as ctx2:
            TavilyAdapter(cfg2, key=None)
        self.assertEqual(ctx2.exception.code, "configuration_error")

    async def test_tavily_explicit_zero_usd_per_credit_preserved(self) -> None:
        config = make_config("tavily", limit=1, pricing={"usd_per_credit": "0"})
        payload: dict[str, object] = {
            "results": [{"url": "https://example.com/item", "title": "Item"}],
            "usage": {"credits": 5},
        }
        transport = DummyTransport(payload)
        adapter = TavilyAdapter(config, key="secret-key")
        resp = await adapter.search("query", transport)
        self.assertEqual(resp.cost.estimated_usd, Decimal("0"))
        self.assertEqual(resp.cost.line_items[0].unit_price_usd, Decimal("0"))

    async def test_brave_pricing_override_applied(self) -> None:
        config = make_config(
            "brave",
            limit=1,
            pricing={
                "rate_per_request": "0.009",
                "plan": "enterprise-custom",
                "mode": "enterprise",
                "as_of": "2026-03-01",
                "version": "1.0",
                "basis": "direct-contract",
            },
        )
        payload: dict[str, object] = {
            "web": {"results": [{"url": "https://example.com/item", "title": "Item"}]}
        }
        transport = DummyTransport(payload)
        adapter = BraveAdapter(config, key="brave-key")
        resp = await adapter.search("query", transport)
        self.assertEqual(resp.cost.estimated_usd, Decimal("0.009"))
        self.assertEqual(
            resp.cost.price_snapshot,
            {
                "wire_mode": "keyed",
                "plan": "enterprise-custom",
                "mode": "enterprise",
                "as_of": "2026-03-01",
                "version": "1.0",
                "basis": "direct-contract",
                "cost_per_request_usd": "0.009",
            },
        )

    async def test_exa_search_success_with_reported_cost_and_latency(self) -> None:
        config = make_config("exa", limit=3, options={"type": "auto"})
        payload: dict[str, object] = {
            "results": [
                {
                    "url": "https://example.com/item1?param=1",
                    "title": "Item 1",
                    "highlights": ["Key snippet text"],
                    "text": "Full text of item 1",
                    "author": "Alice",
                    "publishedDate": "2026-01-01",
                    "score": 0.88,
                    "scores": {"relevance": 0.88},
                    "id": "exa-123",
                },
                {
                    "url": "https://example.com/item2",
                    "title": "Item 2",
                    "summary": "Summary text",
                    "score": 0.75,
                },
            ],
            "searchTime": 0,  # Valid 0 ms latency must be preserved
            "requestId": "req-exa-999",
            "costDollars": {"total": 0.007},
        }
        transport = DummyTransport(payload)
        adapter = ExaAdapter(config, key="exa-test-key")

        resp = await adapter.search("quantum computing", transport)

        self.assertIsInstance(resp, SearchResponse)
        self.assertEqual(resp.provider, "exa")
        self.assertEqual(resp.query, "quantum computing")
        self.assertEqual(len(resp.results), 2)

        # Result 1 fields
        r1 = resp.results[0]
        self.assertEqual(r1.rank, 1)
        self.assertEqual(r1.provider_rank, 1)
        self.assertEqual(r1.url, "https://example.com/item1?param=1")
        self.assertEqual(r1.title, "Item 1")
        self.assertEqual(r1.snippet, "Key snippet text")
        self.assertEqual(r1.content, "Full text of item 1")
        self.assertEqual(r1.author, "Alice")
        self.assertEqual(r1.published_at, "2026-01-01")
        self.assertEqual(r1.score, 0.88)
        self.assertEqual(r1.scores.get("relevance"), 0.88)
        self.assertEqual(r1.metadata.get("id"), "exa-123")

        # Result 2 summary
        r2 = resp.results[1]
        self.assertEqual(r2.summary, "Summary text")

        # Latency & Request ID
        self.assertEqual(resp.provider_reported_latency_ms, 0.0)
        self.assertEqual(resp.provider_request_id, "req-exa-999")

        # Cost reported
        self.assertEqual(resp.cost.source, "reported")
        self.assertEqual(resp.cost.reported_usd, Decimal("0.007"))
        self.assertEqual(resp.cost.total_usd, Decimal("0.007"))

        # Transport verification
        self.assertEqual(len(transport.recorded_requests), 1)
        req = transport.recorded_requests[0]
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["headers"]["x-api-key"], "exa-test-key")
        self.assertEqual(req["json"]["query"], "quantum computing")
        self.assertEqual(req["json"]["numResults"], 3)

    async def test_exa_rates_override_applied(self) -> None:
        config = make_config(
            "exa",
            limit=1,
            options={"type": "instant"},
            pricing={"rates": {"instant": "0.003"}},
        )
        payload: dict[str, object] = {
            "results": [{"url": "https://example.com/item", "title": "Item"}]
        }
        transport = DummyTransport(payload)
        adapter = ExaAdapter(config, key="exa-test-key")
        resp = await adapter.search("instant query", transport)
        self.assertEqual(resp.cost.estimated_usd, Decimal("0.003"))
        self.assertEqual(resp.cost.line_items[0].unit_price_usd, Decimal("0.003"))

    async def test_exa_rejects_credential_urls_and_preserves_provider_rank(self) -> None:
        config = make_config("exa", limit=3)
        payload: dict[str, object] = {
            "results": [
                {"url": "https://user:pass@example.com/secret", "title": "Bad 1"},
                {"url": "https://example.com/good1?param=clean", "title": "Good 1"},
                {"url": "not-a-valid-url", "title": "Bad 2"},
                {"url": "https://example.com/good2", "title": "Good 2"},
            ],
            "searchTime": 90,
        }
        transport = DummyTransport(payload)
        adapter = ExaAdapter(config, key="exa-test-key")

        resp = await adapter.search("security check", transport)

        self.assertEqual(len(resp.results), 2)
        # Good 1: raw index was 1 -> provider_rank=2; final rank=1
        self.assertEqual(resp.results[0].rank, 1)
        self.assertEqual(resp.results[0].provider_rank, 2)
        self.assertEqual(resp.results[0].url, "https://example.com/good1?param=clean")

        # Good 2: raw index was 3 -> provider_rank=4; final rank=2
        self.assertEqual(resp.results[1].rank, 2)
        self.assertEqual(resp.results[1].provider_rank, 4)
        self.assertEqual(resp.results[1].url, "https://example.com/good2")

    async def test_nonempty_all_invalid_results_fail(self) -> None:
        config = make_config("exa", limit=3)
        payload: dict[str, object] = {
            "results": [
                {"url": "https://user:pass@example.com/bad1", "title": "Bad 1"},
                {"url": "invalid://not-http", "title": "Bad 2"},
            ],
            "searchTime": 50,
        }
        transport = DummyTransport(payload)
        adapter = ExaAdapter(config, key="exa-test-key")

        with self.assertRaises(SearchProviderError) as ctx:
            await adapter.search("query", transport)
        self.assertEqual(ctx.exception.code, "invalid_response")

    async def test_exa_semantic_error_raises_search_provider_error(self) -> None:
        config = make_config("exa")
        payload: dict[str, object] = {"error": "Quota exceeded", "status": "error"}
        transport = DummyTransport(payload)
        adapter = ExaAdapter(config, key="exa-test-key")

        with self.assertRaises(SearchProviderError) as ctx:
            await adapter.search("fail query", transport)
        self.assertEqual(ctx.exception.provider, "exa")
        self.assertEqual(ctx.exception.code, "provider_error")
        self.assertEqual(ctx.exception.status_code, 200)
        self.assertTrue(ctx.exception.retryable)

    def test_exa_unknown_option_rejected(self) -> None:
        config = make_config("exa", options={"unknown_option": "value"})
        with self.assertRaises(SearchProviderError) as ctx:
            ExaAdapter(config, key="key")
        self.assertEqual(ctx.exception.code, "bad_request")

    def test_exa_missing_api_key_raises_configuration_error(self) -> None:
        config = make_config("exa")
        with self.assertRaises(SearchProviderError) as ctx:
            ExaAdapter(config, key=None)
        self.assertEqual(ctx.exception.code, "configuration_error")
        self.assertFalse(ctx.exception.retryable)

    async def test_tavily_search_keyed_and_response_time_numeric_string(self) -> None:
        config = make_config("tavily", limit=2, options={"search_depth": "advanced"})
        payload: dict[str, object] = {
            "results": [
                {
                    "url": "https://tavily.example.com/page",
                    "title": "Tavily Title",
                    "content": "Snippet from page",
                    "score": 0.91,
                    "raw_content": "Extracted raw markdown",
                    "published_date": "2026-03-01",
                }
            ],
            "response_time": "0.45",  # numeric string seconds
            "request_id": "tavily-req-1",
            "usage": {"credits": 2},
        }
        transport = DummyTransport(payload)
        adapter = TavilyAdapter(config, key="tavily-secret")

        resp = await adapter.search("deep analysis", transport)

        self.assertEqual(resp.provider, "tavily")
        self.assertEqual(len(resp.results), 1)
        self.assertEqual(resp.results[0].title, "Tavily Title")
        self.assertEqual(resp.results[0].snippet, "Snippet from page")
        self.assertEqual(resp.results[0].content, "Extracted raw markdown")

        # Latency: "0.45" sec -> 450.0 ms
        self.assertEqual(resp.provider_reported_latency_ms, 450.0)
        self.assertEqual(resp.provider_request_id, "tavily-req-1")

        # Cost: 2 credits * $0.008 = $0.016
        self.assertEqual(resp.cost.source, "estimated")
        self.assertEqual(resp.cost.estimated_usd, Decimal("0.016"))

        req = transport.recorded_requests[0]
        self.assertEqual(req["headers"]["Authorization"], "Bearer tavily-secret")
        self.assertEqual(req["json"]["search_depth"], "advanced")
        self.assertEqual(req["json"]["include_usage"], True)

    async def test_tavily_latency_overflow_safety(self) -> None:
        config = make_config("tavily", limit=2)
        payload: dict[str, object] = {
            "results": [{"url": "https://example.com/safe", "title": "Safe"}],
            "response_time": "1e308",  # Multiplied by 1000 would overflow float
        }
        transport = DummyTransport(payload)
        adapter = TavilyAdapter(config, key="key")
        resp = await adapter.search("query", transport)
        self.assertIsNone(resp.provider_reported_latency_ms)

    async def test_tavily_keyless_mode_free_cost(self) -> None:
        config = make_config("tavily", limit=2)
        payload: dict[str, object] = {
            "results": [{"url": "https://example.com/free", "title": "Free Item"}],
            "response_time": 0.22,
            "usage": {"credits": 1},
        }
        transport = DummyTransport(payload)
        adapter = TavilyAdapter(config, key=None)

        resp = await adapter.search("keyless query", transport)

        req = transport.recorded_requests[0]
        self.assertNotIn("Authorization", req["headers"])
        self.assertEqual(req["headers"]["X-Tavily-Access-Mode"], "keyless")
        self.assertEqual(resp.cost.total_usd, Decimal("0"))
        self.assertEqual(
            resp.cost.price_snapshot,
            {
                "wire_mode": "keyless",
                "plan": "keyless-free",
                "mode": "keyless",
                "usd_per_credit": "0",
            },
        )

    async def test_tavily_semantic_error_handling(self) -> None:
        config = make_config("tavily")
        payload: dict[str, object] = {"error": "Invalid API key or rate limit"}
        transport = DummyTransport(payload)
        adapter = TavilyAdapter(config, key="some-key")

        with self.assertRaises(SearchProviderError) as ctx:
            await adapter.search("query", transport)
        self.assertEqual(ctx.exception.provider, "tavily")
        self.assertEqual(ctx.exception.code, "provider_error")

    async def test_brave_web_search_success_and_pricing(self) -> None:
        config = make_config(
            "brave",
            limit=2,
            options={
                "country": "US",
                "search_lang": "en",
                "location": {"city": "New York", "country": "US"},
            },
        )
        payload: dict[str, object] = {
            "web": {
                "results": [
                    {
                        "url": "https://brave.example.com/1",
                        "title": "Brave 1",
                        "description": "Snippet 1",
                        "page_age": "2026-02-15",
                        "language": "en",
                        "family_friendly": True,
                    },
                    {
                        "url": "https://brave.example.com/2",
                        "title": "Brave 2",
                        "description": "Snippet 2",
                    },
                ]
            }
        }
        transport = DummyTransport(payload)
        adapter = BraveAdapter(config, key="brave-key-abc")

        resp = await adapter.search("privacy search", transport)

        self.assertEqual(resp.provider, "brave")
        self.assertEqual(len(resp.results), 2)
        self.assertEqual(resp.results[0].title, "Brave 1")
        self.assertEqual(resp.results[0].snippet, "Snippet 1")
        self.assertEqual(resp.results[0].published_at, "2026-02-15")
        self.assertEqual(resp.results[0].metadata.get("language"), "en")
        self.assertEqual(resp.results[0].metadata.get("family_friendly"), True)

        # Brave reports no latency in payload
        self.assertIsNone(resp.provider_reported_latency_ms)

        # Brave cost: $0.005 per request
        self.assertEqual(resp.cost.source, "estimated")
        self.assertEqual(resp.cost.estimated_usd, Decimal("0.005"))

        req = transport.recorded_requests[0]
        self.assertEqual(req["method"], "GET")
        self.assertEqual(req["headers"]["X-Subscription-Token"], "brave-key-abc")
        self.assertEqual(req["headers"]["X-Loc-City"], "New York")
        self.assertEqual(req["params"]["q"], "privacy search")
        self.assertEqual(req["params"]["count"], 2)
        self.assertEqual(req["params"]["country"], "US")

    async def test_brave_zero_result_search_is_an_empty_success(self) -> None:
        # Brave omits `web` when an exact-phrase query matches nothing.
        payload: dict[str, object] = {
            "type": "search",
            "query": {"original": '"no such exact phrase"'},
            "mixed": {"type": "mixed", "main": [], "top": [], "side": []},
        }
        resp = await BraveAdapter(make_config("brave"), key="key").search(
            '"no such exact phrase"', DummyTransport(payload)
        )
        self.assertEqual(resp.results, [])
        self.assertEqual(resp.total_results, 0)
        self.assertEqual(resp.cost.estimated_usd, Decimal("0.005"))

        with self.assertRaises(SearchProviderError) as ctx:
            await BraveAdapter(make_config("brave"), key="key").search(
                "q", DummyTransport({"type": "search", "query": {}, "web": []})
            )
        self.assertEqual(ctx.exception.code, "invalid_response")

    async def test_brave_semantic_error_response(self) -> None:
        config = make_config("brave")
        payload: dict[str, object] = {"type": "ErrorResponse", "error": "Unauthorized"}
        transport = DummyTransport(payload)
        adapter = BraveAdapter(config, key="bad-key")

        with self.assertRaises(SearchProviderError) as ctx:
            await adapter.search("bad", transport)
        self.assertEqual(ctx.exception.provider, "brave")
        self.assertEqual(ctx.exception.code, "provider_error")

    async def test_firecrawl_search_success_with_channels_and_markdown(self) -> None:
        config = make_config(
            "firecrawl",
            limit=3,
            options={"scrape_options": {"formats": ["markdown"]}},
        )
        payload: dict[str, object] = {
            "success": True,
            "data": {
                "web": [
                    {
                        "url": "https://firecrawl.example.com/doc",
                        "title": "Doc Page",
                        "description": "Short description",
                        "markdown": "# Heading\n\nFull page markdown body.",
                        "metadata": {
                            "author": "Tech Team",
                            "statusCode": 200,
                            "language": "en",
                        },
                    }
                ],
                "news": [],
            },
            "creditsUsed": 2,
            "requestId": "fc-req-555",
        }
        transport = DummyTransport(payload)
        adapter = FirecrawlAdapter(config, key="fc-test-key")

        resp = await adapter.search("scrape docs", transport)

        self.assertEqual(resp.provider, "firecrawl")
        self.assertEqual(len(resp.results), 1)
        r = resp.results[0]
        self.assertEqual(r.title, "Doc Page")
        self.assertEqual(r.snippet, "Short description")
        self.assertEqual(r.markdown, "# Heading\n\nFull page markdown body.")
        self.assertEqual(r.author, "Tech Team")
        self.assertEqual(r.metadata.get("status_code"), 200)
        self.assertEqual(r.metadata.get("source"), "web")

        # Firecrawl cost: 2 credits * $0.0038 = $0.0076
        self.assertEqual(resp.cost.source, "estimated")
        self.assertEqual(resp.cost.estimated_usd, Decimal("0.0076"))

        req = transport.recorded_requests[0]
        self.assertEqual(req["headers"]["Authorization"], "Bearer fc-test-key")
        self.assertEqual(req["json"]["scrapeOptions"], {"formats": ["markdown"]})

    async def test_firecrawl_http200_success_false_fails(self) -> None:
        config = make_config("firecrawl")
        payload: dict[str, object] = {"success": False, "error": "Search rate limit exceeded"}
        transport = DummyTransport(payload)
        adapter = FirecrawlAdapter(config, key="fc-key")

        with self.assertRaises(SearchProviderError) as ctx:
            await adapter.search("rate limit check", transport)
        self.assertEqual(ctx.exception.provider, "firecrawl")
        self.assertEqual(ctx.exception.code, "provider_error")
        self.assertEqual(ctx.exception.status_code, 200)
        self.assertTrue(ctx.exception.retryable)

    def test_adapter_exports(self) -> None:
        for cls in (BraveAdapter, ExaAdapter, FirecrawlAdapter, TavilyAdapter):
            self.assertTrue(issubclass(cls, ProviderAdapter))

    def test_embedded_query_and_limit_options_rejected_before_io(self) -> None:
        # Exa rejects query and num_results in options
        with self.assertRaises(SearchProviderError) as ctx1:
            ExaAdapter(make_config("exa", options={"query": "test"}), key="key")
        self.assertEqual(ctx1.exception.code, "bad_request")

        with self.assertRaises(SearchProviderError) as ctx2:
            ExaAdapter(make_config("exa", options={"num_results": 10}), key="key")
        self.assertEqual(ctx2.exception.code, "bad_request")

        # Tavily rejects query and max_results in options
        with self.assertRaises(SearchProviderError) as ctx3:
            TavilyAdapter(make_config("tavily", options={"query": "test"}), key="key")
        self.assertEqual(ctx3.exception.code, "bad_request")

        with self.assertRaises(SearchProviderError) as ctx4:
            TavilyAdapter(make_config("tavily", options={"max_results": 10}), key="key")
        self.assertEqual(ctx4.exception.code, "bad_request")

        # Brave rejects q and count in options
        with self.assertRaises(SearchProviderError) as ctx5:
            BraveAdapter(make_config("brave", options={"q": "test"}), key="key")
        self.assertEqual(ctx5.exception.code, "bad_request")

        with self.assertRaises(SearchProviderError) as ctx6:
            BraveAdapter(make_config("brave", options={"count": 10}), key="key")
        self.assertEqual(ctx6.exception.code, "bad_request")

        # Firecrawl rejects query and limit in options
        with self.assertRaises(SearchProviderError) as ctx7:
            FirecrawlAdapter(make_config("firecrawl", options={"query": "test"}), key="key")
        self.assertEqual(ctx7.exception.code, "bad_request")

        with self.assertRaises(SearchProviderError) as ctx8:
            FirecrawlAdapter(make_config("firecrawl", options={"limit": 10}), key="key")
        self.assertEqual(ctx8.exception.code, "bad_request")


if __name__ == "__main__":
    unittest.main()
