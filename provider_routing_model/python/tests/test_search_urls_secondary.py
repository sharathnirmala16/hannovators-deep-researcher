"""Offline wire-contract and normalization tests for secondary search APIs."""

from __future__ import annotations

import asyncio
import unittest
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from search_urls.configuration import SearchConfig
from search_urls.providers import create_adapter
from search_urls.providers_secondary import (
    KeenableAdapter,
    ParallelAdapter,
    TinyfishAdapter,
    YouAdapter,
)
from search_urls.transport import AttemptObservation, ObservedPayload, SearchProviderError


def config(
    provider: str,
    *,
    limit: int = 2,
    options: dict[str, Any] | None = None,
    pricing: dict[str, Any] | None = None,
) -> SearchConfig:
    values: dict[str, Any] = {
        "schemaVersion": "search-collection-config/v1",
        "provider": provider,
        "limit": limit,
        "options": options or {},
    }
    if pricing is not None:
        values["pricing"] = pricing
    return SearchConfig.model_validate(values)


class FakeTransport:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Any = None,
        params: Any = None,
        json: Any = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "params": dict(params or {}),
                "json": json,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.payload

    def for_query(self, *_args: Any, **_kwargs: Any) -> FakeTransport:
        return self


class SecondaryProviderTests(unittest.TestCase):
    def test_keenable_uses_public_path_and_preserves_native_order_without_dedup(self):
        transport = FakeTransport(
            {
                "results": [
                    {"url": "https://example.com/a", "title": "A", "position": 1},
                    {"url": "https://example.com/a", "title": "A duplicate", "position": 2},
                    {"url": "https://example.com/ignored", "position": 3},
                ]
            }
        )
        adapter = KeenableAdapter(
            config("keenable", options={"mode": "pro", "site": "example.com"})
        )

        response = asyncio.run(adapter.search("  exact query  ", transport))

        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["url"], "https://api.keenable.ai/v1/search/public")
        self.assertEqual(call["headers"], {"X-Keenable-Title": "provider-evals"})
        self.assertEqual(call["json"]["query"], "  exact query  ")
        self.assertEqual(call["json"]["max_results"], 2)
        self.assertEqual([result.title for result in response.results], ["A", "A duplicate"])
        self.assertEqual([result.provider_rank for result in response.results], [1, 2])
        self.assertEqual(response.cost.estimated_usd, Decimal(0))
        self.assertEqual(response.cost.source, "estimated")

    def test_keenable_paid_realtime_without_native_tariff_stays_unknown(self):
        transport = FakeTransport(
            {
                "results": [{"url": "https://example.com/"}],
                "_meta": {"keenable/usage": {"sku": "search.realtime", "credits": 3, "paid": True}},
            }
        )
        adapter = KeenableAdapter(config("keenable", options={"mode": "realtime"}), "key")

        response = asyncio.run(adapter.search("query", transport))

        self.assertIsNone(response.cost.reported_usd)
        self.assertIsNone(response.cost.estimated_usd)
        self.assertEqual(response.cost.source, "unknown")
        self.assertEqual(response.cost.line_items[0].quantity, 3)
        self.assertIsNone(response.cost.line_items[0].unit_price_usd)
        self.assertEqual(response.cost.native_usage["keenable/usage"]["sku"], "search.realtime")

    def test_parallel_locks_query_and_limit_and_keeps_scores_usage_and_price(self):
        transport = FakeTransport(
            {
                "search_id": "run-123",
                "results": [
                    {
                        "url": "https://example.com/one",
                        "title": "One",
                        "excerpts": ["first", "second"],
                        "position": 1,
                        "score": 0.94,
                    },
                    {"url": "https://example.com/one", "position": 2, "score": 0.9},
                    {"url": "https://example.com/three", "position": 3},
                ],
                "usage": [{"sku": "search", "count": 1}],
            }
        )
        adapter = ParallelAdapter(
            config(
                "parallel",
                options={"mode": "turbo"},
            ),
            "secret",
        )

        response = asyncio.run(adapter.search("query", transport))

        body = transport.calls[0]["json"]
        self.assertEqual(body["objective"], "query")
        self.assertEqual(body["search_queries"], ["query"])
        self.assertEqual(body["mode"], "turbo")
        self.assertEqual(body["advanced_settings"]["max_results"], 2)
        self.assertEqual(
            [result.url for result in response.results],
            [
                "https://example.com/one",
                "https://example.com/one",
            ],
        )
        self.assertEqual(response.results[0].snippet, "first\n\nsecond")
        self.assertEqual(response.results[0].score, 0.94)
        self.assertEqual(response.cost.estimated_usd, Decimal("0.001"))
        self.assertEqual(response.cost.native_usage, [{"sku": "search", "count": 1.0}])
        self.assertEqual(response.provider_request_id, "run-123")

    def test_parallel_rejects_query_options(self):
        transport = FakeTransport({"results": []})
        with self.assertRaises(SearchProviderError):
            adapter = ParallelAdapter(config("parallel", options={"objective": "query"}), "key")
            asyncio.run(adapter.search("query", transport))
        self.assertEqual(transport.calls, [])

    def test_tinyfish_encodes_domain_lists_and_retries_semantic_200_as_safe_error(self):
        transport = FakeTransport({"success": False, "error": "private provider body"})
        adapter = TinyfishAdapter(
            config("tinyfish", options={"include_domains": ["example.com", "docs.example.com"]}),
            "key",
        )

        with self.assertRaises(SearchProviderError) as raised:
            asyncio.run(adapter.search("query", transport))

        self.assertEqual(raised.exception.code, "semantic_error")
        self.assertTrue(raised.exception.retryable)
        self.assertNotIn("private provider body", str(raised.exception))
        self.assertEqual(transport.calls[0]["method"], "GET")
        self.assertEqual(transport.calls[0]["params"]["query"], "query")
        self.assertEqual(
            transport.calls[0]["params"]["include_domains"], "example.com,docs.example.com"
        )

    def test_you_search_preserves_web_then_news_rank_and_uses_explicit_search_price(self):
        transport = FakeTransport(
            {
                "results": {
                    "web": [
                        {
                            "url": "https://example.com/web",
                            "title": "Web result",
                            "position": 1,
                            "favicon_url": "https://example.com/icon.png",
                        }
                    ],
                    "news": [
                        {"url": "https://example.com/news", "title": "News result", "position": 2}
                    ],
                },
                "latency_ms": 127.5,
            }
        )
        adapter = YouAdapter(
            config("you", limit=2, options={"country": "US", "safesearch": "strict"}),
            "secret",
        )

        response = asyncio.run(adapter.search("query", transport))

        body = transport.calls[0]["json"]
        self.assertEqual(body["query"], "query")
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["country"], "US")
        self.assertEqual(
            [result.metadata["section"] for result in response.results], ["web", "news"]
        )
        self.assertEqual(response.provider_reported_latency_ms, 127.5)
        self.assertEqual(response.cost.estimated_usd, Decimal("0.005"))
        self.assertEqual(response.cost.price_snapshot["asOf"], "2026-10-05")

    def test_you_extraction_options_are_mapped_to_native_wire_fields(self):
        transport = FakeTransport({"results": {"web": []}})
        adapter = YouAdapter(
            config(
                "you",
                options={
                    "extraction": {
                        "mode": "highlights",
                        "source": "blend",
                        "highlights": {"total_max_tokens": 2048},
                    }
                },
            ),
            "key",
        )

        asyncio.run(adapter.search("query", transport))

        self.assertEqual(
            transport.calls[0]["json"]["extraction"],
            {
                "extraction_mode": "highlights",
                "extraction_source": "blend",
                "highlights": {"total_max_tokens": 2048},
            },
        )

    def test_invalid_url_results_are_recorded_and_all_invalid_response_fails(self):
        partial_transport = FakeTransport(
            {
                "results": [
                    {"url": "https://example.com/good", "position": 1},
                    {"url": "https://example.com/bad?api_key=secret", "position": 2},
                ]
            }
        )
        response = asyncio.run(YouAdapter(config("you"), "key").search("query", partial_transport))
        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.provider_metadata["rejected_results"][0]["providerRank"], 2)

        invalid_transport = FakeTransport(
            {"results": [{"url": "https://example.com/bad?api_key=secret", "position": 1}]}
        )
        with self.assertRaises(SearchProviderError):
            asyncio.run(YouAdapter(config("you"), "key").search("query", invalid_transport))

    def test_collects_valid_results_past_malformed_items_until_limit(self):
        transport = FakeTransport(
            {
                "results": [
                    {"url": "javascript:alert(1)", "position": 1},
                    {"url": "https://example.com/first", "position": 2},
                    {"url": "https://example.com/second", "position": 3},
                    {"url": "https://example.com/after-limit", "position": 4},
                ]
            }
        )

        response = asyncio.run(YouAdapter(config("you", limit=2), "key").search("query", transport))

        self.assertEqual([result.rank for result in response.results], [1, 2])
        self.assertEqual([result.provider_rank for result in response.results], [2, 3])
        self.assertEqual(response.provider_metadata["rejected_results"][0]["providerRank"], 1)

    def test_explicit_price_overrides_drive_estimate_and_wire_mode(self):
        payload = {
            "results": [
                {"url": f"https://example.com/{index}", "position": index} for index in range(1, 12)
            ]
        }
        settings = config(
            "parallel",
            limit=11,
            options={"mode": "fast"},
            pricing={
                "mode": "fast",
                "ratePerRequest": "0.002",
                "rates": {"extra_result": 0.003},
            },
        )
        response = asyncio.run(ParallelAdapter(settings, "key").search("q", FakeTransport(payload)))

        self.assertEqual(response.cost.estimated_usd, Decimal("0.005"))
        self.assertEqual(response.cost.line_items[0].unit_price_usd, Decimal("0.002"))

    def test_pricing_mode_must_match_wire_mode_before_dispatch(self):
        settings = config(
            "parallel",
            options={"mode": "advanced"},
            pricing={"mode": "turbo"},
        )
        transport = FakeTransport({"results": []})

        with self.assertRaises(SearchProviderError):
            asyncio.run(ParallelAdapter(settings, "key").search("query", transport))
        self.assertEqual(transport.calls, [])

    def test_unknown_option_is_rejected_before_dispatch(self):
        transport = FakeTransport({"results": []})
        adapter = YouAdapter(config("you", options={"count": 100}), "key")
        with self.assertRaises(SearchProviderError):
            asyncio.run(adapter.search("query", transport))
        self.assertEqual(transport.calls, [])

    def test_transport_reported_usage_cost_and_request_id_are_preserved(self):
        payload = ObservedPayload(
            {"results": [{"url": "https://example.com/"}]},
            AttemptObservation(
                http_status=200,
                latency_ms=10,
                reported_usd="0.003",
                source="reported",
                native_usage={"usage": [{"count": 1}]},
                price_snapshot={"provider": "you", "version": "vendor"},
                request_id="header-123",
            ),
        )
        adapter = YouAdapter(config("you"), "key")

        response = asyncio.run(adapter.search("query", FakeTransport(payload)))

        self.assertEqual(response.provider_request_id, "header-123")
        self.assertEqual(response.cost.reported_usd, Decimal("0.003"))
        self.assertEqual(response.cost.source, "reported")
        self.assertEqual(response.cost.native_usage, {"usage": [{"count": 1}]})
        self.assertEqual(response.cost.price_snapshot, {"provider": "you", "version": "vendor"})

    def test_factory_routes_secondary_adapters_and_resolves_env_without_printing(self):
        import os

        old = os.environ.get("TINYFISH_API_KEY")
        os.environ["TINYFISH_API_KEY"] = "env-only-key"
        try:
            self.assertIsInstance(create_adapter(config("tinyfish")), TinyfishAdapter)
            self.assertEqual(create_adapter(config("tinyfish")).api_key, "env-only-key")
        finally:
            if old is None:
                os.environ.pop("TINYFISH_API_KEY", None)
            else:
                os.environ["TINYFISH_API_KEY"] = old

    def test_malformed_config_still_uses_strict_pydantic_boundary(self):
        with self.assertRaises(ValidationError):
            config("parallel", options={"headers": {"Authorization": "secret"}})


if __name__ == "__main__":
    unittest.main()
