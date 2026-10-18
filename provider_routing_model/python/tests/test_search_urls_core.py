"""Focused offline tests for search collection models, storage, and transport."""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import httpx
from pydantic import ValidationError

from search_urls.configuration import SearchConfig, load_config
from search_urls.models import (
    CaseResultRecord,
    CostEvidence,
    CostLineItem,
    SearchResponse,
    SearchResult,
    parse_benchmark_case,
)
from search_urls.persistence import RunStore, load_benchmark
from search_urls.transport import AttemptContext, HttpxJsonTransport, SearchProviderError


def make_config() -> SearchConfig:
    return SearchConfig.model_validate(
        {
            "schemaVersion": "search-collection-config/v1",
            "provider": "exa",
            "limit": 5,
            "options": {"type": "auto", "contents": {"highlights": True}},
            "rateLimits": [{"requests": 20, "windowMs": 1000}],
            "maxConcurrency": 2,
            "limits": {
                "requestTimeoutMs": 1000,
                "queryTimeoutMs": 5000,
                "maxRequestsPerQuery": 5,
                "maxRetries": 1,
            },
        }
    )


def result_record(
    store: RunStore,
    *,
    query: str,
    response: SearchResponse | None,
    case_id: str = "case-1",
    attempt_ids: list[str] | None = None,
    response_attempt_ids: list[str] | None = None,
) -> CaseResultRecord:
    return CaseResultRecord(
        run_id=store.run_id,
        dataset_sha256=store.dataset_sha256,
        config_sha256=store.config_sha256,
        case_id=case_id,
        query=query,
        query_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest(),
        repetition=0,
        provider="exa",
        status="success",
        started_at="2026-10-17T12:00:00Z",
        finished_at="2026-10-17T12:00:01Z",
        invocation_id="invocation-1",
        client_latency_ms=1000,
        provider_reported_latency_ms=(
            response.provider_reported_latency_ms if response is not None else None
        ),
        response=response,
        attempt_ids=attempt_ids or [],
        response_attempt_ids=response_attempt_ids or [],
        cost_scope="response" if response_attempt_ids else "unknown",
    )


def billed_response(query: str) -> SearchResponse:
    return SearchResponse(
        query=query,
        provider="exa",
        results=[
            SearchResult(
                rank=1,
                provider_rank=4,
                title="A result",
                url="https://example.test/path?q=%2F#section",
                content="body",
                summary="summary",
                markdown="**body**",
                author="Ada",
                score=0.8,
                scores={"hybrid": 1},
                metadata={"source": "native"},
            )
        ],
        total_results=1,
        provider_reported_latency_ms=12.375,
        provider_request_id="req-123",
        cost=CostEvidence(
            reported_usd=Decimal("0.007"),
            native_usage={"requests": 1, "credits": 2},
            price_snapshot={"version": "v1", "basis": "reported"},
            line_items=[
                CostLineItem(
                    name="search",
                    quantity=Decimal("1"),
                    unit="request",
                    total_usd=Decimal("0.007"),
                    source="reported",
                )
            ],
        ),
    )


class SearchModelTests(unittest.TestCase):
    def test_example_config_is_strict_and_keeps_native_options(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        config = load_config(repo_root / "benchmarks/configs/search_configs/exa.json")
        self.assertEqual(config.provider, "exa")
        self.assertEqual(config.limit, 5)
        self.assertEqual(
            (config.rate_limits[0].requests, config.rate_limits[0].window_ms), (1, 1000)
        )
        self.assertEqual(config.max_concurrency, 4)
        self.assertEqual(config.options["contents"], {"highlights": True})

        with self.assertRaises(ValidationError):
            SearchConfig.model_validate(
                {
                    "schemaVersion": "search-collection-config/v1",
                    "provider": "exa",
                    "rateLimits": [],
                }
            )

    def test_config_rejects_nested_credential_headers_without_echo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "provider.json"
            for settings in (
                {"options": {"nested": [{"headers": {"X-Api-Key": "VALUE_MUST_NOT_ECHO_1"}}]}},
                {"pricing": {"rates": {"nested": {"X-Auth-Token": "VALUE_MUST_NOT_ECHO_2"}}}},
            ):
                config = {
                    "schemaVersion": "search-collection-config/v1",
                    "provider": "exa",
                    **settings,
                }
                config_path.write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaisesRegex(
                    ValueError, "invalid search collection config"
                ) as caught:
                    load_config(config_path)
                self.assertNotIn("VALUE_MUST_NOT_ECHO", str(caught.exception))

            invalid_price = {
                "schemaVersion": "search-collection-config/v1",
                "provider": "exa",
                "pricing": {"usdPerCredit": True},
            }
            config_path.write_text(json.dumps(invalid_price), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid search collection config") as caught:
                load_config(config_path)
            self.assertNotIn("True", str(caught.exception))

    def test_public_case_keeps_query_and_rejects_reference_fields(self) -> None:
        case = parse_benchmark_case({"id": "case-1", "prompt": "  exact query?  "})
        self.assertEqual(case.query, "  exact query?  ")
        with self.assertRaises(ValueError):
            parse_benchmark_case({"id": "case-1", "prompt": "query", "answer": "private answer"})
        with self.assertRaises(ValueError):
            parse_benchmark_case(
                {"id": "case-1", "prompt": "query", "goldUrls": ["https://example.test"]}
            )

    def test_evidence_url_is_preserved_and_credentials_are_rejected(self) -> None:
        url = "https://example.test/a?q=%2f#section"
        self.assertEqual(SearchResult(url=url).url, url)
        with self.assertRaises(ValidationError):
            SearchResult(url="https://example.test/a?api_key=secret")

    def test_billed_response_and_result_json_round_trip(self) -> None:
        query = "  exact query?\n"
        response = billed_response(query)
        response_copy = SearchResponse.model_validate_json(response.model_dump_json(by_alias=True))
        self.assertEqual(response_copy.provider_reported_latency_ms, 12.375)
        self.assertEqual(response_copy.cost.total_usd, Decimal("0.007"))
        self.assertEqual(response_copy.results[0].provider_rank, 4)
        self.assertEqual(response_copy.results[0].url, "https://example.test/path?q=%2F#section")

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.jsonl"
            input_path.write_text(json.dumps({"id": "case-1", "prompt": query}) + "\n")
            with RunStore(
                Path(directory) / "runs", "roundtrip", make_config(), input_path
            ) as store:
                record = result_record(store, query=query, response=response_copy)
                parsed = CaseResultRecord.model_validate_json(record.model_dump_json(by_alias=True))
                self.assertEqual(parsed.response.cost.total_usd, Decimal("0.007"))
                store.append_result(record)

    def test_estimated_cost_requires_a_pinned_price_basis(self) -> None:
        with self.assertRaises(ValidationError):
            CostEvidence(estimated_usd=Decimal("0.01"))
        evidence = CostEvidence(
            estimated_usd=Decimal("0.01"),
            price_snapshot={"basis": "configured rate", "version": "v1"},
        )
        self.assertEqual(evidence.total_usd, Decimal("0.01"))


class RunStoreTests(unittest.TestCase):
    def test_input_snapshot_billed_resume_and_additive_ids(self) -> None:
        raw = b'{"id":"case-1","prompt":" exact query? "}\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "questions.jsonl"
            input_path.write_bytes(raw)
            captured, cases, digest = load_benchmark(input_path, input_bytes=raw)
            self.assertEqual(captured, raw)
            self.assertEqual(cases[0].query, " exact query? ")
            self.assertEqual(digest, hashlib.sha256(raw).hexdigest())

            output_root = root / "runs"
            with RunStore(
                output_root, "resume", make_config(), input_path, input_bytes=raw
            ) as store:
                self.assertEqual(store.input_snapshot_path.read_bytes(), raw)
                context = _attempt_context("case-1")
                failed_id = store.begin_attempt(
                    context, "POST", "https://api.example/search?q=private"
                )
                store.finish_attempt(
                    failed_id, status="error", http_status=500, error_code="http_error"
                )
                success_id = store.begin_attempt(context, "POST", "https://api.example/search")
                store.finish_attempt(success_id, status="success", http_status=200)

                response = billed_response(" exact query? ")
                store.reconcile_attempt_costs([success_id], response.cost)
                store.append_result(
                    result_record(
                        store,
                        query=" exact query? ",
                        response=response,
                        attempt_ids=[failed_id, success_id],
                        response_attempt_ids=[success_id],
                    )
                )
                self.assertEqual(store.request_count("case-1"), 2)
                self.assertEqual(store.completed_ids(), {"case-1"})

            with RunStore(
                output_root, "resume", make_config(), input_path, input_bytes=raw
            ) as store:
                self.assertEqual(store.request_count("case-1"), 2)
                self.assertEqual(store.result_states()[("case-1", 0)].status, "success")
                self.assertEqual(store.completed_ids(), {"case-1"})
                rows = [json.loads(line) for line in store.attempts_path.read_text().splitlines()]
                costs = [row for row in rows if row.get("event") == "cost"]
                self.assertEqual(len(costs), 1)
                self.assertEqual(costs[0]["responseAttemptIds"], [success_id])
                self.assertEqual(costs[0]["reportedUsd"], "0.007")
                self.assertNotIn("q=private", store.attempts_path.read_text())

            extended = raw + b'{"id":"case-2","prompt":"new question"}\n'
            input_path.write_bytes(extended)
            with RunStore(output_root, "resume", make_config(), input_path) as store:
                self.assertEqual({case.case_id for case in store.cases}, {"case-1", "case-2"})
                self.assertEqual(
                    store.manifest["datasetSHA256"], hashlib.sha256(extended).hexdigest()
                )

    def test_changed_or_removed_existing_query_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "questions.jsonl"
            input_path.write_text('{"id":"case-1","prompt":"first"}\n')
            output_root = root / "runs"
            with RunStore(output_root, "fixed", make_config(), input_path):
                pass

            input_path.write_text('{"id":"case-1","prompt":"changed"}\n')
            with (
                self.assertRaisesRegex(ValueError, "changed an existing query"),
                RunStore(output_root, "fixed", make_config(), input_path),
            ):
                pass

            input_path.write_text('{"id":"case-2","prompt":"replacement"}\n')
            with (
                self.assertRaisesRegex(ValueError, "removed an existing case"),
                RunStore(output_root, "fixed", make_config(), input_path),
            ):
                pass

    def test_nonsecret_access_mode_is_pinned_across_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "questions.jsonl"
            input_path.write_text('{"id":"case-1","prompt":"query"}\n')
            output_root = root / "runs"
            with RunStore(output_root, "mode", make_config(), input_path) as store:
                store.pin_runtime_settings({"accessMode": "keyless"})
                self.assertEqual(store.manifest["runtimeSettings"], {"accessMode": "keyless"})

            with RunStore(output_root, "mode", make_config(), input_path) as store:
                store.pin_runtime_settings({"accessMode": "keyless"})
                with self.assertRaisesRegex(ValueError, "access mode changed"):
                    store.pin_runtime_settings({"accessMode": "keyed"})
                self.assertNotIn("apiKey", store.manifest["runtimeSettings"])

    def test_initial_manifest_recovery_and_unmatched_start_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "questions.jsonl"
            raw = b'{"id":"case-1","prompt":"query"}\n'
            input_path.write_bytes(raw)
            output_root = root / "runs"
            crashed = RunStore(output_root, "crashed", make_config(), input_path)
            crashed.inputs_dir.mkdir(parents=True)
            crashed.input_snapshot_path.write_bytes(crashed.input_bytes)
            with crashed as store:
                self.assertTrue(store.manifest_path.exists())
                attempt_id = store.begin_attempt(
                    _attempt_context("case-1"), "POST", "https://api.example/search"
                )

            with crashed.attempts_path.open("ab") as stream:
                stream.write(b'{"event":"unfinished partial')
            with RunStore(output_root, "crashed", make_config(), input_path) as recovered:
                rows = [
                    json.loads(line) for line in recovered.attempts_path.read_text().splitlines()
                ]
                self.assertEqual(rows[-1]["event"], "finished")
                self.assertEqual(rows[-1]["attemptId"], attempt_id)
                self.assertEqual(rows[-1]["status"], "cancelled")
                self.assertEqual(recovered.request_count("case-1"), 1)

            with crashed.attempts_path.open("ab") as stream:
                stream.write(b'{"event":"bad","runId":"crashed"}\n')
            with (
                self.assertRaisesRegex(ValueError, "attempt journal row is missing an ID"),
                RunStore(output_root, "crashed", make_config(), input_path),
            ):
                pass

    def test_malformed_terminated_result_row_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "questions.jsonl"
            input_path.write_text('{"id":"case-1","prompt":"query"}\n')
            output_root = root / "runs"
            with RunStore(output_root, "bad-result", make_config(), input_path) as store:
                store.results_path.write_bytes(b'{"runId":"bad-result"}\n')
            with (
                self.assertRaisesRegex(ValueError, "malformed terminated result journal row"),
                RunStore(output_root, "bad-result", make_config(), input_path),
            ):
                pass


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_physical_start_precedes_dispatch_and_http_observations_persist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "questions.jsonl"
            input_path.write_text(
                '{"id":"case-1","prompt":"first"}\n'
                '{"id":"case-2","prompt":"second"}\n'
                '{"id":"case-3","prompt":"third"}\n'
            )
            store_context = RunStore(root / "runs", "transport", make_config(), input_path)
            with store_context as store:
                entered_handler = asyncio.Event()

                async def handler(request: httpx.Request) -> httpx.Response:
                    rows = [
                        json.loads(line) for line in store.attempts_path.read_text().splitlines()
                    ]
                    starts = [row for row in rows if row.get("event") == "started"]
                    self.assertTrue(starts)
                    self.assertEqual(starts[-1]["method"], request.method)
                    self.assertNotIn("?", starts[-1]["url"])
                    if request.url.path == "/semantic":
                        return httpx.Response(
                            200,
                            json={
                                "blocked": True,
                                "costDollars": {"total": 0.007},
                                "usage": {
                                    "credits": 2,
                                    "auditUrl": "https://vendor.example/?signature=private",
                                },
                                "requestId": "req-200",
                            },
                        )
                    if request.url.path == "/limited":
                        return httpx.Response(
                            429,
                            headers={"Retry-After": "0.25"},
                            json={"reportedUsd": 0.003, "usage": {"credits": 1}},
                        )
                    entered_handler.set()
                    await asyncio.Event().wait()
                    raise AssertionError("unreachable")

                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    transport = HttpxJsonTransport(
                        client,
                        "exa",
                        journal=store,
                        request_timeout_ms=2000,
                        rate_limits=((20, 1000),),
                        max_concurrency=2,
                    )
                    semantic = transport.for_query("case-1", 0, 0, 3)
                    await semantic.request("POST", "https://api.example/semantic?query=private")
                    semantic.finish_query("error", "blocked")

                    limited = transport.for_query("case-2", 0, 0, 3)
                    with self.assertRaises(SearchProviderError) as caught:
                        await limited.request("POST", "https://api.example/limited")
                    self.assertEqual(caught.exception.status_code, 429)
                    self.assertGreaterEqual(caught.exception.retry_after_seconds or 0, 0.2)

                    cancelled = transport.for_query("case-3", 0, 0, 3)
                    task = asyncio.create_task(
                        cancelled.request("POST", "https://api.example/cancel")
                    )
                    await entered_handler.wait()
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

                rows = [json.loads(line) for line in store.attempts_path.read_text().splitlines()]
                finished = [row for row in rows if row.get("event") == "finished"]
                self.assertEqual(
                    [row["status"] for row in finished], ["error", "error", "cancelled"]
                )
                self.assertEqual(finished[0]["httpStatus"], 200)
                self.assertEqual(finished[0]["reportedUsd"], "0.007")
                self.assertEqual(finished[0]["requestId"], "req-200")
                self.assertEqual(
                    finished[0]["nativeUsage"],
                    {
                        "costDollars": {"total": 0.007},
                        "usage": {
                            "credits": 2,
                            "auditUrl": "[redacted-url]",
                        },
                    },
                )
                self.assertEqual(finished[1]["httpStatus"], 429)
                self.assertEqual(finished[1]["reportedUsd"], "0.003")
                self.assertEqual(finished[2]["errorCode"], "cancelled")


def _attempt_context(case_id: str) -> AttemptContext:
    return AttemptContext(
        case_id=case_id,
        repetition=0,
        retry=0,
        provider="exa",
        request_cap=5,
    )


if __name__ == "__main__":
    unittest.main()
