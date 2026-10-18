"""Offline Jev request, sampler, cache, retry, and budget tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

from query_gold_test_helpers import make_cases

from query_gold.jev import (
    DEFAULT_THRESHOLDS,
    EXPECTED_ANSWER_IDS,
    JEV_CALIBRATION_VERSION,
    JEV_ENDPOINT,
    JEV_MAX_PHYSICAL_REQUESTS,
    JEV_MODEL,
    JEV_TIMEOUT_SECONDS,
    CommandCodeJevClient,
    JevConfig,
    JevReviewer,
    _calibration_candidates,
    api_key_from_environment,
    run_jev_review,
    stratified_sample,
    zero_data_retention_requested,
)
from query_gold.models import QueryGoldCase
from query_gold.validation import CATEGORY_IDS


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(self, handler: Callable[[Any, int], FakeResponse]) -> None:
        self.handler = handler
        self.calls: list[Any] = []
        self.before_call: Callable[[int], None] | None = None

    def post(self, request: Any, *, timeout: float) -> FakeResponse:
        index = len(self.calls) + 1
        if self.before_call:
            self.before_call(index)
        self.calls.append(request)
        self.assert_timeout = timeout
        return self.handler(request, index)

    def close(self) -> None:
        pass


class FakeTransport:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.url = ""
        self.headers: dict[str, str] = {}
        self.body: dict[str, Any] = {}
        self.timeout = 0.0

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float):
        self.url = url
        self.headers = headers
        self.body = json
        self.timeout = timeout
        return self.response

    def close(self) -> None:
        pass


def success_payload(*, negative: bool = False) -> dict[str, Any]:
    probabilities = {question_id: 0.99 for question_id in EXPECTED_ANSWER_IDS}
    if negative:
        probabilities["gold_supported"] = 0.01
    return {
        "model": "typesafe/jev",
        "answers": {
            question_id: {"type": "noul", "noul": value}
            for question_id, value in probabilities.items()
        },
        "usage": {"input_tokens": 120, "output_tokens": 35, "cost_usd": 0.001},
    }


def fixture_cases(root: Path):
    return make_cases(root, count_per_category=5)


def best_buy_finance_case() -> QueryGoldCase:
    excerpt = (
        "Revenue ($ in millions)\n"
        " Enterprise                                                         $     9,583"
        "    $   10,329\n"
    )
    return QueryGoldCase.model_validate(
        {
            "schemaVersion": "query-gold/v1",
            "id": "fin-bby-q2fy24-enterprise-revenue",
            "categoryId": "01_earnings_corporate_finance",
            "query": (
                "For Best Buy Q2 FY2024, the 13-week quarter ended 2023-07-29, what was "
                "Enterprise revenue in USD millions?"
            ),
            "temporal": {"kind": "version", "precision": "version", "version": "Q2 FY2024"},
            "gold": {
                "answer": "$     9,583",
                "value": 9583.0,
                "acceptedAnswers": ["$     9,583"],
                "units": "USD million",
                "currency": "USD",
            },
            "evidence": [
                {
                    "url": (
                        "https://s2.q4cdn.com/785564492/files/doc_earnings/2024/q2/"
                        "earnings-result/Best-Buy-Reports-Fiscal-Second-Quarter-Results.pdf"
                    ),
                    "title": "Best Buy Reports Second Quarter Results (Q2 FY2024)",
                    "retrievedAtUTC": "2026-10-17T15:50:00Z",
                    "publishedAt": "2023-08-29",
                    "sourceRecordId": "bby-q2fy24",
                    "upstreamRevision": "cc39aeb4afdf33909ee1412188bf89035950c2eb",
                    "license": "unknown",
                    "rawSha256": "0" * 64,
                    "rawPath": "raw/best-buy-q2fy24.txt",
                    "excerpt": excerpt,
                }
            ],
            "derivation": {
                "sourceFamily": "official_earnings_release",
                "generatorVersion": "query-gold/v1",
                "questionType": "quarterly_segment_revenue",
            },
        },
        strict=True,
    )


class QueryGoldJevTests(unittest.TestCase):
    def test_calibration_uses_real_case_and_counterfactual_gold_support_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            positive, negative = _calibration_candidates([best_buy_finance_case()])
            self.assertEqual(positive.state["query"], negative.state["query"])
            self.assertEqual(positive.state["temporal"], negative.state["temporal"])
            self.assertEqual(positive.state["evidence"], negative.state["evidence"])
            self.assertIn("9,583", positive.state["evidence"][0]["excerpt"])
            self.assertEqual(
                positive.state["evidence"][0]["url"],
                "https://s2.q4cdn.com/785564492/files/doc_earnings/2024/q2/"
                "earnings-result/Best-Buy-Reports-Fiscal-Second-Quarter-Results.pdf",
            )
            self.assertNotEqual(positive.state["gold"]["answer"], negative.state["gold"]["answer"])
            self.assertNotEqual(positive.state["gold"]["value"], negative.state["gold"]["value"])
            self.assertEqual(negative.state["gold"]["acceptedAnswers"], [])
            self.assertNotEqual(positive.case_sha256, negative.case_sha256)
            self.assertEqual(positive.calibration_expected, "positive")
            self.assertEqual(negative.calibration_expected, "negative")
            self.assertEqual(JEV_CALIBRATION_VERSION, "query-gold-jev-calibration/v2")

            reviewer = JevReviewer(None, Path(temporary))
            positive_result = {
                "caseId": "calibration-positive",
                "status": "valid_response",
                "probabilities": {question_id: 0.99 for question_id in EXPECTED_ANSWER_IDS},
            }
            negative_probabilities = {question_id: 0.01 for question_id in EXPECTED_ANSWER_IDS}
            negative_result = {
                "caseId": "calibration-negative",
                "status": "valid_response",
                "probabilities": negative_probabilities,
            }
            self.assertTrue(reviewer._calibration_passed([positive_result, negative_result]))

            negative_probabilities["gold_supported"] = 0.21
            self.assertFalse(reviewer._calibration_passed([positive_result, negative_result]))
            negative_probabilities["gold_supported"] = 0.01
            positive_result["probabilities"]["direct_search_answerable"] = 0.79
            self.assertFalse(reviewer._calibration_passed([positive_result, negative_result]))

    def test_deterministic_sampler_spreads_cases_across_question_types(self):
        with tempfile.TemporaryDirectory() as temporary:
            cases = fixture_cases(Path(temporary))
            first = stratified_sample(cases, seed=17)
            second = stratified_sample(cases, seed=17)
            self.assertEqual([case.id for case in first], [case.id for case in second])
            self.assertEqual(len(first), 3 * len(CATEGORY_IDS))
            for category in CATEGORY_IDS:
                selected = [case for case in first if case.categoryId == category]
                self.assertEqual(len(selected), 3)
                self.assertEqual(len({case.derivation.questionType for case in selected}), 3)

    def test_request_adapter_pins_endpoint_model_questions_and_does_not_log_headers(self):
        transport = FakeTransport(FakeResponse(200, success_payload()))
        client = CommandCodeJevClient("synthetic-test-key", transport=transport)
        # The transport is deliberately local; this test makes no HTTP request.
        from query_gold.jev import RUBRIC_QUESTIONS, JevQuestion, JevRequest

        request = JevRequest(
            model=JEV_MODEL,
            state=json.dumps(
                {"query": "What was the value?", "gold": {"answer": "10"}},
                separators=(",", ":"),
            ),
            questions={
                question_id: JevQuestion.model_validate(question, strict=True)
                for question_id, question in RUBRIC_QUESTIONS.items()
            },
        )
        client.post(request, timeout=JEV_TIMEOUT_SECONDS)
        self.assertEqual(transport.url, JEV_ENDPOINT)
        self.assertEqual(transport.body["model"], "typesafe/jev-1.14.0")
        self.assertEqual(set(transport.body["questions"]), EXPECTED_ANSWER_IDS)
        self.assertTrue(
            all(question["type"] == "noul" for question in transport.body["questions"].values())
        )
        self.assertIn(
            "direct search",
            transport.body["questions"]["direct_search_answerable"]["instructions"].casefold(),
        )
        self.assertIsInstance(transport.body["state"], str)
        self.assertEqual(json.loads(transport.body["state"])["query"], "What was the value?")
        self.assertEqual(transport.timeout, JEV_TIMEOUT_SECONDS)
        self.assertIn("synthetic-test-key", transport.headers["Authorization"])
        client.close()

    def test_success_persists_each_attempt_before_the_next_call_and_caches_decisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = fixture_cases(root)
            client = FakeClient(
                lambda request, _: FakeResponse(
                    200,
                    success_payload(
                        negative=(
                            json.loads(request.state)["gold"]["answer"]
                            not in " ".join(
                                evidence["excerpt"]
                                for evidence in json.loads(request.state)["evidence"]
                            )
                        )
                    ),
                )
            )
            reviewer = JevReviewer(client, root, config=JevConfig(seed=17))

            def assert_previous_attempt_was_durable(call_number: int) -> None:
                if call_number == 1:
                    return
                report = json.loads(reviewer.report_path.read_text(encoding="utf-8"))
                self.assertEqual(len(report["attempts"]), call_number - 1)
                previous = report["attempts"][-1]
                self.assertIn("completedAtUTC", previous)
                self.assertIn("usage", previous)
                self.assertIn("probabilities", previous)
                self.assertNotIn("headers", previous)
                self.assertNotIn("Authorization", json.dumps(previous))

            client.before_call = assert_previous_attempt_was_durable
            report = reviewer.run(cases)
            self.assertTrue(report["calibration"]["passed"])
            expected_logical = 2 + 3 * len(CATEGORY_IDS)
            self.assertEqual(report["physicalRequests"], expected_logical)
            self.assertEqual(len(report["attempts"]), expected_logical)
            self.assertEqual(len(report["results"]), 3 * len(CATEGORY_IDS))
            self.assertTrue(all(result["status"] == "pass" for result in report["results"]))
            self.assertEqual(
                report["reviewCoverage"]["unsampledCaseCount"], len(cases) - 3 * len(CATEGORY_IDS)
            )
            self.assertFalse(report["reviewCoverage"]["allCasesAutomaticallyReviewed"])
            self.assertAlmostEqual(
                report["cost"]["reportedUsdTotal"], (2 + 3 * len(CATEGORY_IDS)) * 0.001
            )
            self.assertIsNone(report["cost"]["estimatedUsd"])

            no_call_client = FakeClient(
                lambda _request, _index: self.fail("cache should skip calls")
            )
            cached_reviewer = JevReviewer(no_call_client, root, config=JevConfig(seed=17))
            cached_report = cached_reviewer.run(cases)
            self.assertEqual(no_call_client.calls, [])
            self.assertEqual(cached_report["physicalRequests"], 0)
            self.assertEqual(cached_report["cacheHits"], expected_logical)

    def test_invalid_responses_retry_once_then_remain_review_required_under_shared_cap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = fixture_cases(root)
            client = FakeClient(
                lambda _request, _index: FakeResponse(
                    200,
                    {"answers": {"gold_supported": {"noul": 1.0}}, "usage": {"input_tokens": 1}},
                )
            )
            config = JevConfig(max_physical_requests=3, sample_per_category=1, seed=3)
            reviewer = JevReviewer(client, root, config=config)
            report = reviewer.run(cases)

            self.assertEqual(len(client.calls), 3)
            self.assertEqual(report["physicalRequests"], 3)
            self.assertLessEqual(report["physicalRequests"], JEV_MAX_PHYSICAL_REQUESTS)
            self.assertFalse(report["calibration"]["passed"])
            self.assertTrue(report["attempts"])
            self.assertTrue(
                all(result["status"] == "review_required" for result in report["results"])
            )
            self.assertTrue(all(result.get("decision") != "PASS" for result in report["results"]))
            self.assertTrue(
                all(attempt["status"] == "invalid_response" for attempt in report["attempts"])
            )

    def test_retry_is_persisted_and_successful_calibration_does_not_hide_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = fixture_cases(root)

            def handler(request: Any, call_number: int) -> FakeResponse:
                if call_number == 1:
                    return FakeResponse(200, {"answers": {}, "usage": {}})
                state = json.loads(request.state)
                return FakeResponse(
                    200,
                    success_payload(
                        negative=state["gold"]["answer"]
                        not in " ".join(item["excerpt"] for item in state["evidence"])
                    ),
                )

            client = FakeClient(handler)
            reviewer = JevReviewer(client, root, config=JevConfig(seed=9))
            persisted_before_retry: list[str] = []

            def checkpoint(call_number: int) -> None:
                if call_number == 2:
                    saved = json.loads(reviewer.report_path.read_text(encoding="utf-8"))
                    persisted_before_retry.extend(item["status"] for item in saved["attempts"])

            client.before_call = checkpoint
            report = reviewer.run(cases)
            self.assertEqual(persisted_before_retry, ["invalid_response"])
            self.assertEqual(report["physicalRequests"], 2 + 3 * len(CATEGORY_IDS) + 1)
            self.assertTrue(report["calibration"]["passed"])
            self.assertEqual(report["attempts"][0]["errorCode"], "invalid_response")
            self.assertNotIn("error", report["attempts"][0])

    def test_zdr_requirement_returns_clear_unsupported_status_without_client_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = fixture_cases(root)
            report, path = run_jev_review(
                cases,
                root,
                api_key=None,
                zdr_requested=True,
            )
            self.assertEqual(report["status"], "unsupported_zdr_requested")
            self.assertEqual(report["physicalRequests"], 0)
            self.assertTrue(path.is_file())

    def test_environment_aliases_and_request_bounds_are_explicit(self):
        self.assertEqual(
            api_key_from_environment(
                {"CMD_API_KEY": "preferred", "COMMANDCODE_API_KEY": "secondary"}
            ),
            "preferred",
        )
        self.assertEqual(
            api_key_from_environment({"COMMANDCODE_KEY": "runtime-alias"}), "runtime-alias"
        )
        self.assertTrue(zero_data_retention_requested({"CMD_ZERO_DATA_RETENTION": "yes"}))
        self.assertTrue(zero_data_retention_requested({"CMD_ZDR": "1"}))
        self.assertFalse(zero_data_retention_requested({"CMD_ZERO_DATA_RETENTION": "false"}))
        self.assertEqual(set(DEFAULT_THRESHOLDS), EXPECTED_ANSWER_IDS)
        with self.assertRaises(ValueError):
            JevConfig(max_physical_requests=JEV_MAX_PHYSICAL_REQUESTS + 1)
        with self.assertRaises(ValueError):
            JevConfig(timeout_seconds=JEV_TIMEOUT_SECONDS + 1)


if __name__ == "__main__":
    unittest.main()
