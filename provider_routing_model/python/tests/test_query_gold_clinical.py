"""Focused offline tests for ClinicalTrials.gov source extraction and snapshots."""

from __future__ import annotations

import hashlib
import json
import stat
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

import httpx

PYTHON_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PYTHON_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from query_gold.categories import clinical  # noqa: E402
from query_gold.models import QueryGoldCase  # noqa: E402

RETRIEVED_AT = "2026-10-17T15:50:00Z"
SEED = clinical.TRIALS[0]


def fixture_study() -> dict[str, object]:
    """A minimal API record with intentionally distinct date and unit fields."""
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": SEED.nct_id,
                "briefTitle": "Synthetic registry fixture for parser tests",
            },
            "statusModule": {
                "overallStatus": "RECRUITING",
                "lastUpdatePostDateStruct": {"date": "2024-12-04", "type": "ACTUAL"},
                "primaryCompletionDateStruct": {"date": "2027-06-01", "type": "ESTIMATED"},
                "completionDateStruct": {"date": "2027-12-31", "type": "ESTIMATED"},
            },
            "designModule": {"phases": ["PHASE3"]},
            "outcomesModule": {
                "primaryOutcomes": [
                    {
                        "measure": "Change in the synthetic symptom score",
                        "description": "A deliberately different explanatory field.",
                        "timeFrame": "12 weeks",
                        "units": "points",
                    }
                ]
            },
        }
    }


class ClinicalExtractionTests(unittest.TestCase):
    def test_seed_set_preserves_distinct_studies_and_date_phase_mix(self) -> None:
        self.assertEqual(len(clinical.TRIALS), 25)
        self.assertEqual(len({seed.nct_id for seed in clinical.TRIALS}), 25)
        statuses = Counter(seed.overall_status for seed in clinical.TRIALS)
        self.assertEqual(statuses, {"RECRUITING": 6, "COMPLETED": 19})
        secondary_types = Counter(seed.secondary_question for seed in clinical.TRIALS)
        self.assertEqual(
            secondary_types,
            {"overall_completion_date": 13, "registry_phase": 12},
        )

    def test_overall_completion_is_not_primary_completion_and_keeps_type(self) -> None:
        status = {
            "primaryCompletionDateStruct": {"date": "2027-06-01", "type": "ESTIMATED"},
            "completionDateStruct": {"date": "2027-12", "type": "ACTUAL"},
        }
        self.assertEqual(clinical._completion(status), ("2027-12", "month", "Actual"))

        with self.assertRaisesRegex(ValueError, "overall completion"):
            clinical._completion(
                {"primaryCompletionDateStruct": {"date": "2027-06-01", "type": "ACTUAL"}}
            )

    def test_estimated_and_actual_completion_labels_are_not_conflated(self) -> None:
        self.assertEqual(
            clinical._completion(
                {"completionDateStruct": {"date": "2027-12-31", "type": "ESTIMATED"}}
            ),
            ("2027-12-31", "day", "Estimated"),
        )
        self.assertEqual(
            clinical._completion({"completionDateStruct": {"date": "2020-03", "type": "ACTUAL"}}),
            ("2020-03", "month", "Actual"),
        )

    def test_invalid_or_invented_completion_date_precision_is_rejected(self) -> None:
        for invalid_date in ("2024-02-30", "2024-13", "2024-02-03T00:00:00Z", None):
            with self.subTest(invalid_date=invalid_date), self.assertRaises(ValueError):
                clinical._completion(
                    {"completionDateStruct": {"date": invalid_date, "type": "ACTUAL"}}
                )
        with self.assertRaisesRegex(ValueError, "ACTUAL or ESTIMATED"):
            clinical._completion({"completionDateStruct": {"date": "2024-02", "type": "PLANNED"}})

    def test_phase_parser_rejects_unknown_labels_and_formats_registry_values(self) -> None:
        phases = clinical._phase_values({"phases": ["PHASE1", "PHASE2"]})
        self.assertEqual(clinical._phase_answer(phases), "Phase 1 and Phase 2")
        with self.assertRaisesRegex(ValueError, "unknown registry phase"):
            clinical._phase_values({"phases": ["FDA_APPROVED"]})

    def test_primary_measure_does_not_substitute_description_timeframe_or_units(self) -> None:
        outcome = {
            "measure": "Change in the synthetic symptom score",
            "description": "Not the measure label",
            "timeFrame": "12 weeks",
            "units": "points",
        }
        self.assertEqual(
            clinical._primary_measure({"primaryOutcomes": [outcome]}), outcome["measure"]
        )
        with self.assertRaisesRegex(ValueError, "measure field"):
            clinical._primary_measure({"primaryOutcomes": [{"timeFrame": "12 weeks"}]})


class ClinicalSnapshotIntegrationTests(unittest.TestCase):
    def test_reparse_raw_parent_is_rejected_before_fetch_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "category"
            raw_dir = output_dir / "raw"
            raw_dir.mkdir(parents=True)
            original_lstat = Path.lstat
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

            def fake_lstat(path: Path) -> object:
                if path == raw_dir:
                    return SimpleNamespace(
                        st_mode=stat.S_IFDIR,
                        st_file_attributes=reparse_flag,
                    )
                return original_lstat(path)

            with (
                patch.object(Path, "lstat", fake_lstat),
                patch.object(httpx, "Client") as http_client,
                self.assertRaisesRegex(ValueError, "reparse-point"),
            ):
                clinical.collect(output_dir, count=1)

            http_client.assert_not_called()
            self.assertFalse((raw_dir / "requests.jsonl").exists())
            self.assertFalse((raw_dir / "studies").exists())

    def test_cached_api_payload_exports_valid_versioned_query_gold_cases(self) -> None:
        payload = fixture_study()
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        study_url = f"{clinical.API_STUDY_URL}{SEED.nct_id}"
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            raw_path = output_dir / "raw" / "studies" / f"{SEED.nct_id}.json"
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(body)
            metadata_path = raw_path.with_name(f"{SEED.nct_id}.meta.json")
            metadata_path.write_text(
                json.dumps(
                    {
                        "url": study_url,
                        "retrievedAtUTC": RETRIEVED_AT,
                        "rawSha256": hashlib.sha256(body).hexdigest(),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(httpx, "Client") as http_client:
                records = clinical.collect(output_dir, count=2)
            http_client.assert_not_called()

            self.assertEqual(len(records), 2)
            outcome, completion = [QueryGoldCase.model_validate(row) for row in records]
            self.assertEqual(outcome.gold.answer, "Change in the synthetic symptom score")
            self.assertEqual(outcome.gold.value, outcome.gold.answer)
            self.assertIsNone(outcome.gold.units)
            self.assertNotIn("12 weeks", outcome.query)
            self.assertIn(SEED.nct_id, outcome.query)
            self.assertTrue(outcome.query.startswith("For ClinicalTrials.gov study "))
            self.assertNotIn(RETRIEVED_AT, outcome.query)
            self.assertNotIn("above", outcome.query.casefold())
            self.assertNotIn("calculate", outcome.query.casefold())
            self.assertEqual(completion.gold.answer, "2027-12-31 (Estimated)")
            self.assertEqual(completion.gold.value, {"date": "2027-12-31", "type": "ESTIMATED"})
            self.assertIn(
                '{"date":"2027-12-31","type":"ESTIMATED"}',
                completion.gold.acceptedAnswers,
            )
            self.assertEqual(completion.temporal.version, "Last Update Posted 2024-12-04")
            self.assertIn("Last Update Posted 2024-12-04", completion.query)
            self.assertIn("Actual/Estimated type", completion.query)
            self.assertNotIn(" and ", completion.query.casefold())
            self.assertNotIn(RETRIEVED_AT, completion.query)
            self.assertEqual(completion.evidence[0].retrievedAtUTC, RETRIEVED_AT)
            self.assertEqual(outcome.evidence[0].rawSha256, hashlib.sha256(body).hexdigest())
            self.assertEqual(outcome.evidence[0].rawPath, f"raw/studies/{SEED.nct_id}.json")
            self.assertEqual(outcome.evidence[0].url, f"{clinical.PUBLIC_STUDY_URL}{SEED.nct_id}")
            self.assertIn(outcome.evidence[0].excerpt, body.decode("utf-8"))
            self.assertIn(
                '"completionDateStruct":{"date":"2027-12-31","type":"ESTIMATED"}', body.decode()
            )

            evidence = outcome.evidence + completion.evidence
            for item in evidence:
                raw = output_dir / item.rawPath
                self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), item.rawSha256)
                self.assertIn(item.excerpt, raw.read_text(encoding="utf-8"))
            self.assertEqual(len({outcome.id, completion.id}), 2)
            self.assertNotEqual(outcome.query, completion.query)

    def test_http_404_is_logged_as_rejected_without_retry_or_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            response = SimpleNamespace(status_code=404)
            client = Mock()
            client.get.return_value = response
            with self.assertRaisesRegex(RuntimeError, "HTTP 404"):
                clinical._fetch_record(output_dir, SEED, cast(httpx.Client, client))
            self.assertEqual(client.get.call_count, 1)
            attempts = [
                json.loads(line)
                for line in (output_dir / "raw" / "requests.jsonl").read_text().splitlines()
            ]
            rejected = [
                json.loads(line)
                for line in (output_dir / "raw" / "rejected.jsonl").read_text().splitlines()
            ]
            self.assertEqual([row["status"] for row in attempts], [404])
            self.assertEqual(rejected[0]["sourceRecordId"], SEED.nct_id)
            self.assertFalse((output_dir / "raw" / "studies" / f"{SEED.nct_id}.json").exists())

    def test_http_redirect_is_one_counted_attempt_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            client = Mock()
            client.get.return_value = SimpleNamespace(status_code=302)
            with (
                patch.object(httpx, "Client", return_value=client) as client_factory,
                self.assertRaisesRegex(RuntimeError, "HTTP 302"),
            ):
                clinical.collect(output_dir, count=1)

            client_factory.assert_called_once()
            self.assertFalse(client_factory.call_args.kwargs["follow_redirects"])
            self.assertEqual(client.get.call_count, 1)
            attempts = [
                json.loads(line)
                for line in (output_dir / "raw" / "requests.jsonl").read_text().splitlines()
            ]
            rejected = [
                json.loads(line)
                for line in (output_dir / "raw" / "rejected.jsonl").read_text().splitlines()
            ]
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]["status"], 302)
            self.assertEqual(rejected[0]["status"], 302)
            self.assertFalse((output_dir / "raw" / "studies" / f"{SEED.nct_id}.json").exists())


if __name__ == "__main__":
    unittest.main()
