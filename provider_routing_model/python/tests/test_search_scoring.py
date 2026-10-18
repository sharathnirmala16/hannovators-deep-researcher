"""Focused offline tests for search relevance scoring and constrained-quality ranking."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any, cast

from search_scoring.categories import category_for
from search_scoring.loading import QueryOutcome, _classify
from search_scoring.ranking import RankingParams, rank_all
from search_scoring.relevance import (
    Relevance,
    answer_profile,
    canonical_url,
    rank_discount,
    score_response,
)
from search_urls.models import SearchResult

GOLD = "https://www.example.gov/reports/q4.pdf"


def result(url: str, text: str = "", rank: int | None = None) -> SearchResult:
    return SearchResult(rank=rank, url=url, title="t", snippet=text)


class RelevanceTests(unittest.TestCase):
    def test_answer_match_normalizes_currency_thousands_mojibake_and_arrows(self) -> None:
        cases = [
            ("$ 14,735", "Enterprise revenue was $14,735 million."),
            ("\u00e2\u201a\u00ac1000,000", "Sold for \u20ac1,000,000 at auction."),
            ("$5.70 to $6.50", "Guidance of $5.70-$6.50 per share"),
            ("610 \u21d2 640", "Base damage: 610 \u2192 640"),
        ]
        for answer, text in cases:
            with self.subTest(answer=answer):
                score = score_response([result("https://x.test/a", text)], answer, [GOLD])
                self.assertEqual(score.answer_hit, 1.0)

    def test_numeric_match_requires_specific_numbers_close_together(self) -> None:
        def hit(answer: str, text: str) -> float | None:
            return score_response([result("https://x.test/a", text)], answer, [GOLD]).answer_hit

        self.assertEqual(hit("170 W", "default tdp 170w processor"), 1.0)
        self.assertEqual(hit("6.62607015e-34", "h = 6.62607015 \u00d710 -34 J s"), 1.0)
        self.assertEqual(hit("2027-02 (Estimated)", "phase 2 trial; completion 2027"), 0.0)
        self.assertEqual(hit("MS17-010", "windows 10 build 1607, released 2017"), 0.0)
        self.assertEqual(hit("$13.8B", "valued at $13.8 billion"), 1.0)
        far = "revenue 610 " + "x" * 300 + " cost 640"
        self.assertEqual(hit("610 \u21d2 640", far), 0.0)

    def test_short_answers_are_scored_on_url_and_domain_only(self) -> None:
        self.assertFalse(answer_profile("16").informative)
        self.assertFalse(answer_profile("for").informative)
        self.assertTrue(answer_profile("GPIO 2").informative)
        score = score_response([result(GOLD.replace("www.", ""), "16 16 16")], "16", [GOLD])
        self.assertIsNone(score.answer_hit)
        self.assertEqual(score.score, 1.0)

    def test_rank_discount_and_canonical_urls(self) -> None:
        self.assertEqual(
            canonical_url("http://WWW.example.gov/Reports/q4.pdf/?utm_source=x#top"),
            canonical_url(GOLD),
        )
        results = [result("https://other.test/1", rank=1), result(GOLD + "?utm_medium=y", rank=3)]
        score = score_response(results, "Ashish Vaswani", [GOLD])
        self.assertAlmostEqual(score.url_hit, rank_discount(3))
        self.assertEqual(score.url_rank, 3)
        self.assertEqual(score.answer_hit, 0.0)
        self.assertEqual(score_response([], "Ashish Vaswani", [GOLD]).score, 0.0)

    def test_every_category_prefix_resolves(self) -> None:
        self.assertEqual(category_for("code_api_py_re_sub_signature"), "03_code_api_documentation")
        self.assertEqual(category_for("muni-austin-sf3"), "12_municipal_code_zoning_local_law")
        with self.assertRaises(ValueError):
            category_for("unknown-case")


class OutcomeTests(unittest.TestCase):
    def classify(self, **fields: Any) -> tuple[str, str | None]:
        return _classify(cast(Any, SimpleNamespace(**{"response": None, "error": None, **fields})))

    def test_billing_and_budget_errors_are_missing_but_provider_errors_fail(self) -> None:
        error = SimpleNamespace
        self.assertEqual(self.classify(status="cancelled"), ("missing", "cancelled"))
        billing = error(code="http_error", status_code=402)
        self.assertEqual(self.classify(status="error", error=billing), ("missing", "billing_402"))
        budget = error(code="request_limit", status_code=None)
        self.assertEqual(self.classify(status="error", error=budget), ("missing", "request_limit"))
        too_long = error(code="http_error", status_code=422)
        self.assertEqual(self.classify(status="error", error=too_long), ("failure", "http_422"))
        empty = SimpleNamespace(results=[])
        self.assertEqual(
            self.classify(status="success", response=empty), ("failure", "zero_results")
        )
        self.assertEqual(_classify(None), ("missing", "no_record"))


def outcomes(
    provider: str, qualities: list[float | None], *, cost: float = 0.005, latency: float = 900
) -> list[QueryOutcome]:
    rows = []
    for index, quality in enumerate(qualities):
        outcome = "missing" if quality is None else ("success" if quality > 0 else "failure")
        relevance = Relevance(quality, quality, quality, quality, 1, 1) if quality else None
        case_id = f"{'fin' if index % 2 else 'cve'}-{index}"
        rows.append(
            QueryOutcome(
                provider=provider,
                case_id=case_id,
                category=category_for(case_id),
                outcome=outcome,  # type: ignore[arg-type]
                reason=None if outcome == "success" else "zero_results",
                quality=quality,
                relevance=relevance,
                answer_informative=True,
                result_count=5 if outcome == "success" else 0,
                attempts=1,
                latency_ms=None if quality is None else latency,
                cost_usd=None if quality is None else cost,
            )
        )
    return rows


class RankingTests(unittest.TestCase):
    def test_full_ranking_penalizes_failures_and_breaks_quality_ties_by_utility(self) -> None:
        n = 60
        data = {
            "cheap": outcomes("cheap", [0.9] * n, cost=0.004),
            "pricey": outcomes("pricey", [0.9] * n, cost=0.012, latency=4000),
            "flaky": outcomes("flaky", [0.9 if i % 3 == 0 else 0.0 for i in range(n)]),
            "absent": outcomes("absent", [0.9] * 10 + [None] * (n - 10)),
        }
        params = RankingParams(bootstrap=400, seed=1)
        by_category, overall = rank_all(data, params)
        self.assertEqual(len(by_category), 2)
        order = [s.provider for s in overall]
        self.assertEqual(order, ["cheap", "pricey", "flaky", "absent"])
        tiers = {s.provider: s.tier for s in overall}
        self.assertEqual(tiers["cheap"], tiers["pricey"])
        self.assertGreater(tiers["flaky"], tiers["cheap"])
        flaky = next(s for s in overall if s.provider == "flaky")
        self.assertEqual(flaky.stats.failures, 40)
        self.assertLess(flaky.quality, 0.5)
        self.assertEqual(overall[-1].status, "insufficient_coverage")
        for standings in by_category.values():
            self.assertEqual([s.rank for s in standings], [1, 2, 3, 4])

    def test_constraint_violations_rank_below_feasible_providers(self) -> None:
        data = {
            "fast": outcomes("fast", [0.5] * 40),
            "slow": outcomes("slow", [0.95] * 40, latency=20_000),
        }
        _, overall = rank_all(data, RankingParams(bootstrap=200))
        self.assertEqual([s.provider for s in overall], ["fast", "slow"])
        self.assertEqual(overall[1].status, "constraint_violation")


if __name__ == "__main__":
    unittest.main()
