"""Unit tests for scripts/quick_jev_check.py."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_PATH = _REPO_ROOT / "scripts"
if str(_SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_PATH))

from query_gold_test_helpers import make_case  # noqa: E402
from quick_jev_check import (  # noqa: E402
    EvaluationResult,
    QuickJevRunner,
    build_parser,
    format_llm_prompt,
    resolve_api_key,
)

from query_gold.models import QueryGoldCase  # noqa: E402


class TestQuickJevCheck(unittest.TestCase):
    def test_resolve_api_key_explicit(self) -> None:
        self.assertEqual(resolve_api_key("explicit_key_123"), "explicit_key_123")

    def test_resolve_api_key_from_env(self) -> None:
        with patch.dict("os.environ", {"CMD_API_KEY": "env_key_456"}):
            self.assertEqual(resolve_api_key(), "env_key_456")

    def test_format_llm_prompt(self) -> None:
        result = EvaluationResult(
            id="test-case-1",
            categoryId="01_earnings_corporate_finance",
            query="What was Apple Q1 FY24 revenue?",
            goldAnswer="119.58 billion",
            acceptedAnswers=["119.6B"],
            units="USD",
            currency="USD",
            evidenceUrl="https://apple.com/newsroom/q1",
            evidenceExcerpt=(
                "Apple today announced financial results for its fiscal 2024 first quarter "
                "ended December 30, 2023. The Company posted quarterly revenue of $119.58 billion."
            ),
            scores={
                "gold_supported": 0.70,
                "direct_search_answerable": 0.85,
                "single_answer": 0.90,
                "temporal_coherent": 0.95,
            },
            correctnessScore=0.70,
            confidenceScore=0.85,
            passed=False,
            flagReasons=["low_correctness (gold_supported=0.70 < 0.80)"],
        )
        prompt = format_llm_prompt(result)
        self.assertIn("Case ID", prompt)
        self.assertIn("test-case-1", prompt)
        self.assertIn("What was Apple Q1 FY24 revenue?", prompt)
        self.assertIn("119.58 billion", prompt)
        self.assertIn("low_correctness", prompt)
        self.assertIn("[VERIFIED_CORRECT]", prompt)

    def test_dry_run_evaluation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            case_data = make_case("01_earnings_corporate_finance", 1, Path(tmp_dir))
            case = QueryGoldCase.model_validate(case_data)
            cache_path = Path(tmp_dir) / "cache.json"
            runner = QuickJevRunner(api_key=None, cache_path=cache_path, dry_run=True)
            passed, flagged = runner.evaluate_all([case], concurrency=1)
            self.assertEqual(len(passed), 1)
            self.assertEqual(len(flagged), 0)
            self.assertTrue(passed[0].passed)

    def test_runner_flagging_on_low_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            case_data = make_case("01_earnings_corporate_finance", 1, Path(tmp_dir))
            case = QueryGoldCase.model_validate(case_data)
            cache_path = Path(tmp_dir) / "cache.json"
            runner = QuickJevRunner(
                api_key="mock_key",
                cache_path=cache_path,
                correctness_threshold=0.90,
                dry_run=False,
            )
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "model": "typesafe/jev-1.14.0",
                "answers": {
                    "gold_supported": {"type": "noul", "noul": 0.65},
                    "direct_search_answerable": {"type": "noul", "noul": 0.95},
                    "single_answer": {"type": "noul", "noul": 0.95},
                    "temporal_coherent": {"type": "noul", "noul": 0.95},
                },
                "usage": {},
            }
            mock_client.post.return_value = mock_resp
            runner._client = mock_client

            passed, flagged = runner.evaluate_all([case], concurrency=1)
            self.assertEqual(len(passed), 0)
            self.assertEqual(len(flagged), 1)
            self.assertFalse(flagged[0].passed)
            self.assertTrue(any("low_correctness" in r for r in flagged[0].flagReasons))
            self.assertIn("You are an expert fact-checker", flagged[0].llmVerificationPrompt)

    def test_runner_caching_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            case_data = make_case("01_earnings_corporate_finance", 1, Path(tmp_dir))
            case = QueryGoldCase.model_validate(case_data)
            cache_path = Path(tmp_dir) / "cache.json"
            runner = QuickJevRunner(api_key="mock_key", cache_path=cache_path, dry_run=False)
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "model": "typesafe/jev-1.14.0",
                "answers": {
                    "gold_supported": {"type": "noul", "noul": 0.95},
                    "direct_search_answerable": {"type": "noul", "noul": 0.95},
                    "single_answer": {"type": "noul", "noul": 0.95},
                    "temporal_coherent": {"type": "noul", "noul": 0.95},
                },
                "usage": {},
            }
            mock_client.post.return_value = mock_resp
            runner._client = mock_client

            passed1, _ = runner.evaluate_all([case], concurrency=1)
            self.assertEqual(len(passed1), 1)
            self.assertFalse(passed1[0].cached)
            self.assertEqual(mock_client.post.call_count, 1)

            passed2, _ = runner.evaluate_all([case], concurrency=1)
            self.assertEqual(len(passed2), 1)
            self.assertTrue(passed2[0].cached)
            self.assertEqual(mock_client.post.call_count, 1)

    def test_parser_options(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--limit", "5", "--concurrency", "4", "--threshold", "0.85"])
        self.assertEqual(args.limit, 5)
        self.assertEqual(args.concurrency, 4)
        self.assertEqual(args.threshold, 0.85)


if __name__ == "__main__":
    unittest.main()
