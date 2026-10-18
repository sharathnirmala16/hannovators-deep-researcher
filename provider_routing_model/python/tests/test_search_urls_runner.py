"""Offline integration tests for durable search collection and resume behavior."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx

from search_urls.cli import build_parser
from search_urls.configuration import SearchConfig
from search_urls.models import CostEvidence, SearchResponse, SearchResult
from search_urls.persistence import RunStore
from search_urls.runner import (
    SearchCollectionRunner,
    _config_sha256,
    _select_cases,
    run_collection,
)
from search_urls.transport import HttpxJsonTransport, SearchProviderError, SearchTransport


def make_config() -> SearchConfig:
    return SearchConfig.model_validate(
        {
            "schemaVersion": "search-collection-config/v1",
            "provider": "exa",
            "limit": 3,
            "options": {"type": "auto"},
            "rateLimits": [{"requests": 100, "windowMs": 1000}],
            "maxConcurrency": 1,
            "limits": {
                "requestTimeoutMs": 1000,
                "queryTimeoutMs": 5000,
                "maxRequestsPerQuery": 5,
                "maxRetries": 1,
            },
        }
    )


def write_cases(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps({"id": case_id, "prompt": query}) + "\n" for case_id, query in rows),
        encoding="utf-8",
    )


class MockProviderAdapter:
    """Exercise the scoped transport while keeping every request offline."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        self.queries.append(query)
        payload = await transport.request(
            "POST",
            "https://search.example.test/v1/search",
            headers={"authorization": "Bearer fake-test-marker"},
            params={"api_key": "fake-test-marker"},
            json={"query": query},
        )
        if "error" in payload:
            raise SearchProviderError("exa", "semantic_error", status_code=200, retryable=True)
        cost_dollars = payload.get("costDollars")
        total = cost_dollars.get("total") if isinstance(cost_dollars, dict) else None
        if not isinstance(total, str):
            raise SearchProviderError("exa", "invalid_response", retryable=True)
        return SearchResponse(
            query=query,
            provider="exa",
            results=[
                SearchResult(
                    title="Offline result",
                    url="https://example.org/result",
                    snippet="Returned by a mock HTTP transport.",
                )
            ],
            cost=CostEvidence(
                reported_usd=Decimal(total),
                native_usage={"searches": 1},
            ),
        )


class WaitingHttpTransport(httpx.AsyncBaseTransport):
    """Mock request that remains active until its caller is cancelled."""

    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        del request
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("the mock request should only finish through cancellation")


class BrokenAdapter:
    """Dispatch one mock request, then fail during local response processing."""

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse:
        await transport.request(
            "POST",
            "https://search.example.test/v1/search",
            json={"query": query},
        )
        raise RuntimeError("private adapter detail")


class TestSearchCollectionRunner(unittest.IsolatedAsyncioTestCase):
    def test_cli_requires_an_explicit_benchmark(self) -> None:
        parser = build_parser()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args([])
        args = parser.parse_args(["--benchmark", "benchmarks/eval_v2/questions/query_gold.jsonl"])
        self.assertEqual(
            args.benchmark,
            Path("benchmarks/eval_v2/questions/query_gold.jsonl"),
        )

    async def test_retry_resume_new_ids_and_no_credential_zero_pending(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            config = make_config()
            config_path = root / "benchmarks/configs/search_configs/exa.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(config.model_dump(mode="json", by_alias=True), default=str),
                encoding="utf-8",
            )
            input_path = root / "benchmarks/eval_v2/questions/query_gold.jsonl"
            initial_rows = [
                ("alpha:001", "  exact alpha query  "),
                ("beta:002", "Beta query"),
                ("gamma:003", "Gamma query"),
            ]
            extended_rows = [*initial_rows, ("aviation:004", "New category query")]
            write_cases(input_path, initial_rows)

            request_counts: dict[str, int] = {}

            def handler(request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content)
                query = body["query"]
                request_counts[query] = request_counts.get(query, 0) + 1
                if query == "  exact alpha query  " and request_counts[query] == 1:
                    # A semantic error in a successful HTTP response must still retry.
                    return httpx.Response(200, json={"error": "temporarily blocked"})
                return httpx.Response(
                    200,
                    json={
                        "results": [{"url": "https://example.org/result"}],
                        "costDollars": {"total": "0.02"},
                        "usage": {"searches": 1},
                    },
                )

            adapter = MockProviderAdapter()
            invocation_count = 0
            run_root = root / "benchmarks/eval_v2/search_results/exa"

            async def invoke(rows: list[tuple[str, str]], *, max_queries: int) -> dict[str, object]:
                nonlocal invocation_count
                invocation_count += 1
                write_cases(input_path, rows)
                with RunStore(run_root, _config_sha256(config), config, input_path) as store:
                    selection = _select_cases(
                        store.cases,
                        store,
                        retry_failed=False,
                        max_queries=max_queries,
                    )
                    if not selection.cases:
                        return {"selectedIds": [], "summary": None}
                    async with httpx.AsyncClient(
                        transport=httpx.MockTransport(handler), follow_redirects=False
                    ) as client:
                        transport = HttpxJsonTransport(
                            client,
                            config.provider,
                            journal=store,
                            request_timeout_ms=config.limits.request_timeout_ms,
                            rate_limits=[
                                (item.requests, item.window_ms) for item in config.rate_limits
                            ],
                            max_concurrency=config.max_concurrency,
                        )
                        runner = SearchCollectionRunner(
                            config,
                            store,
                            adapter,
                            transport,
                            invocation_id=f"invocation-{invocation_count}",
                            progress=False,
                        )
                        summary = await runner.run(selection)
                    return {
                        "selectedIds": [case.case_id for case in selection.cases],
                        "summary": summary,
                    }

            first = await invoke(initial_rows, max_queries=1)
            self.assertEqual(first["selectedIds"], ["alpha:001"])
            self.assertEqual(first["summary"]["success"], 1)  # type: ignore[index]
            self.assertEqual(first["summary"]["physicalAttempts"], 2)  # type: ignore[index]

            second = await invoke(initial_rows, max_queries=1)
            self.assertEqual(second["selectedIds"], ["beta:002"])
            self.assertEqual(second["summary"]["deferred"], 1)  # type: ignore[index]

            third = await invoke(extended_rows, max_queries=1)
            self.assertEqual(third["selectedIds"], ["gamma:003"])

            fourth = await invoke(extended_rows, max_queries=1)
            self.assertEqual(fourth["selectedIds"], ["aviation:004"])
            self.assertEqual(
                adapter.queries,
                [
                    "  exact alpha query  ",
                    "  exact alpha query  ",
                    "Beta query",
                    "Gamma query",
                    "New category query",
                ],
            )

            run_dir = run_root / _config_sha256(config)
            result_rows = [
                json.loads(line)
                for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            alpha = next(row for row in result_rows if row["caseId"] == "alpha:001")
            self.assertEqual(alpha["query"], "  exact alpha query  ")
            self.assertEqual(len(alpha["attemptIds"]), 2)
            self.assertEqual(len(alpha["responseAttemptIds"]), 1)
            self.assertEqual(alpha["responseAttemptIds"], [alpha["attemptIds"][-1]])
            self.assertEqual(alpha["costScope"], "response")
            self.assertEqual(alpha["response"]["cost"]["reportedUsd"], "0.02")

            attempts = [
                json.loads(line)
                for line in (run_dir / "attempts.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            alpha_finishes = [
                row
                for row in attempts
                if row.get("event") == "finished" and row["attemptId"] in alpha["attemptIds"]
            ]
            self.assertEqual([row["status"] for row in alpha_finishes], ["error", "success"])
            self.assertEqual(alpha_finishes[0]["httpStatus"], 200)
            self.assertEqual(alpha_finishes[0]["errorCode"], "semantic_error")
            cost_events = [row for row in attempts if row.get("event") == "cost"]
            alpha_cost = next(
                row
                for row in cost_events
                if row["responseAttemptIds"] == alpha["responseAttemptIds"]
            )
            self.assertEqual(alpha_cost["reportedUsd"], "0.02")
            self.assertNotIn(
                "fake-test-marker", (run_dir / "attempts.jsonl").read_text(encoding="utf-8")
            )

            # No pending cases means adapter construction and credential resolution are skipped.
            with (
                patch("search_urls.runner.repository_root", return_value=root),
                patch(
                    "search_urls.runner.create_adapter", side_effect=AssertionError("unexpected")
                ),
            ):
                summary = await run_collection(
                    config_path=config_path,
                    benchmark_path=input_path,
                    env_file=root / ".env",
                    progress=False,
                )
            self.assertEqual(summary["selected"], 0)
            self.assertEqual(summary["skippedSuccess"], 4)

    async def test_cancellation_persists_physical_and_case_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = make_config()
            input_path = root / "questions.jsonl"
            write_cases(input_path, [("cancel:001", "Wait for cancellation")])
            journal_transport = WaitingHttpTransport()
            run_root = root / "search-results/exa"

            with RunStore(run_root, _config_sha256(config), config, input_path) as store:
                selection = _select_cases(
                    store.cases,
                    store,
                    retry_failed=False,
                    max_queries=None,
                )
                async with httpx.AsyncClient(transport=journal_transport) as client:
                    transport = HttpxJsonTransport(
                        client,
                        config.provider,
                        journal=store,
                        request_timeout_ms=config.limits.request_timeout_ms,
                        rate_limits=[(100, 1000)],
                        max_concurrency=1,
                    )
                    runner = SearchCollectionRunner(
                        config,
                        store,
                        MockProviderAdapter(),
                        transport,
                        invocation_id="cancel-test",
                        progress=False,
                    )
                    task = asyncio.create_task(runner.run(selection))
                    await asyncio.wait_for(journal_transport.started.wait(), timeout=1)
                    task.cancel()
                    summary = await task

                result = json.loads(store.results_path.read_text(encoding="utf-8").strip())
                attempts = [
                    json.loads(line)
                    for line in store.attempts_path.read_text(encoding="utf-8").splitlines()
                ]

            self.assertEqual(summary["status"], "interrupted")
            self.assertEqual(summary["cancelled"], 1)
            self.assertEqual(result["status"], "cancelled")
            finished = [row for row in attempts if row.get("event") == "finished"]
            self.assertEqual(len(finished), 1)
            self.assertEqual(finished[0]["status"], "cancelled")

    async def test_queued_cases_do_not_spend_query_timeout_waiting_for_a_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = make_config().model_copy(
                update={"limits": make_config().limits.model_copy(update={"query_timeout_ms": 400})}
            )
            input_path = root / "questions.jsonl"
            write_cases(input_path, [(f"queued:{index}", f"Query {index}") for index in range(5)])
            handler = httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"results": [], "costDollars": {"total": "0.01"}}
                )
            )
            with RunStore(
                root / "search-results/exa", _config_sha256(config), config, input_path
            ) as store:
                selection = _select_cases(store.cases, store, retry_failed=False, max_queries=None)
                async with httpx.AsyncClient(transport=handler) as client:
                    transport = HttpxJsonTransport(
                        client,
                        config.provider,
                        journal=store,
                        request_timeout_ms=config.limits.request_timeout_ms,
                        rate_limits=[(1, 150)],
                        max_concurrency=config.max_concurrency,
                    )
                    runner = SearchCollectionRunner(
                        config,
                        store,
                        MockProviderAdapter(),
                        transport,
                        invocation_id="queued-test",
                        progress=False,
                    )
                    summary = await runner.run(selection)

            self.assertEqual(summary["success"], 5)
            self.assertEqual(summary["error"], 0)

    async def test_retry_failed_grants_a_fresh_request_budget_per_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = make_config().model_copy(
                update={
                    "limits": make_config().limits.model_copy(
                        update={"max_requests_per_query": 1, "max_retries": 0}
                    )
                }
            )
            input_path = root / "questions.jsonl"
            write_cases(input_path, [("quota:001", "Quota query")])
            run_root = root / "search-results/exa"
            statuses = iter([402, 200])

            def handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(next(statuses), json={"costDollars": {"total": "0.01"}})

            async def invoke(*, retry_failed: bool) -> dict[str, object]:
                with RunStore(run_root, _config_sha256(config), config, input_path) as store:
                    selection = _select_cases(
                        store.cases, store, retry_failed=retry_failed, max_queries=None
                    )
                    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                        transport = HttpxJsonTransport(
                            client,
                            config.provider,
                            journal=store,
                            request_timeout_ms=config.limits.request_timeout_ms,
                            rate_limits=[(100, 1000)],
                            max_concurrency=1,
                        )
                        runner = SearchCollectionRunner(
                            config,
                            store,
                            MockProviderAdapter(),
                            transport,
                            invocation_id=f"budget-{retry_failed}",
                            progress=False,
                            fresh_request_budget=retry_failed,
                        )
                        return await runner.run(selection)

            first = await invoke(retry_failed=False)
            self.assertEqual(first["error"], 1)
            second = await invoke(retry_failed=True)
            self.assertEqual(second["success"], 1)
            self.assertEqual(second["physicalAttempts"], 1)
            attempts = (run_root / _config_sha256(config) / "attempts.jsonl").read_text("utf-8")
            self.assertEqual(attempts.count('"event":"started"'), 2)

    async def test_unexpected_adapter_error_is_saved_safely_before_reraising(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = make_config()
            input_path = root / "questions.jsonl"
            write_cases(input_path, [("broken:001", "Unexpected adapter failure")])
            run_root = root / "search-results/exa"
            handler = httpx.MockTransport(
                lambda request: httpx.Response(200, json={"usage": {"searches": 1}})
            )

            with RunStore(run_root, _config_sha256(config), config, input_path) as store:
                selection = _select_cases(
                    store.cases,
                    store,
                    retry_failed=False,
                    max_queries=None,
                )
                async with httpx.AsyncClient(transport=handler) as client:
                    transport = HttpxJsonTransport(
                        client,
                        config.provider,
                        journal=store,
                        request_timeout_ms=config.limits.request_timeout_ms,
                        rate_limits=[(100, 1000)],
                        max_concurrency=1,
                    )
                    runner = SearchCollectionRunner(
                        config,
                        store,
                        BrokenAdapter(),
                        transport,
                        invocation_id="broken-adapter-test",
                        progress=False,
                    )
                    with self.assertRaisesRegex(RuntimeError, "private adapter detail"):
                        await runner.run(selection)

                result = json.loads(store.results_path.read_text(encoding="utf-8").strip())
                attempts = [
                    json.loads(line)
                    for line in store.attempts_path.read_text(encoding="utf-8").splitlines()
                ]

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["code"], "internal_error")
            self.assertEqual(len(result["attemptIds"]), 1)
            self.assertEqual(result["responseAttemptIds"], [])
            self.assertEqual(result["costScope"], "attempts")
            self.assertNotIn(
                "private adapter detail",
                (run_root / _config_sha256(config) / "results.jsonl").read_text(encoding="utf-8"),
            )
            finished = [row for row in attempts if row.get("event") == "finished"]
            self.assertEqual(len(finished), 1)
            self.assertEqual(finished[0]["status"], "error")
            self.assertEqual(finished[0]["errorCode"], "internal_error")


if __name__ == "__main__":
    unittest.main()
