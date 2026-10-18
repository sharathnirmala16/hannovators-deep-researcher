"""Critical offline tests for historical facts and exclusion boundaries."""

import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/curate-provider-eval-585.py"
SPEC = importlib.util.spec_from_file_location("temporal_curator", SCRIPT)
assert SPEC and SPEC.loader
curator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(curator)
HistoricalCollector = curator.HistoricalCollector
HistoricalWindow = curator.HistoricalWindow
load_snapshots = curator.load_snapshots


def stamp(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


class TemporalCuratorTests(unittest.TestCase):
    def setUp(self):
        self.window = HistoricalWindow("2026-10-17T09:00:00Z")

    def test_previous_calendar_month_and_cutoff_are_reproducible(self):
        self.assertEqual(self.window.month, "2026-09")
        self.assertEqual(self.window.cutoff_text, "2026-09-30T23:59:59Z")
        self.assertEqual(HistoricalWindow("2026-01-03").month, "2025-12")
        self.assertEqual(HistoricalWindow("2024-03-01").cutoff.day, 29)
        with self.assertRaises(ValueError):
            HistoricalWindow("2026-09-17", "2026-09")
        with self.assertRaises(ValueError):
            HistoricalWindow("2026-10-17T12:00:00")

    def test_yahoo_exact_historical_close_never_adjclose_or_future_bar(self):
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "instrumentType": "EQUITY",
                            "symbol": "AAPL",
                            "dataGranularity": "1d",
                            "exchangeTimezoneName": "America/New_York",
                        },
                        "timestamp": [
                            stamp("2026-09-29T13:30:00Z"),
                            stamp("2026-09-30T13:30:00Z"),
                            stamp("2026-10-01T13:30:00Z"),
                        ],
                        "indicators": {
                            "quote": [{"close": [90, 100.25, 999]}],
                            "adjclose": [{"adjclose": [80, 81, 82]}],
                        },
                    }
                ]
            }
        }
        with patch.object(curator, "request_json", return_value=payload) as request:
            service = HistoricalCollector(SimpleNamespace(**vars(curator)), self.window)
            public, answer = service.yahoo(object(), "Apple", "AAPL", 1, "finance_sec")
        self.assertIn("2026-09-30", public["prompt"])
        self.assertIn("America/New_York", public["prompt"])
        self.assertIn("Yahoo Finance historical Close (not AdjClose)", public["prompt"])
        self.assertEqual(answer["stockEvaluation"]["expectedPrice"], 100.25)
        self.assertEqual(answer["stockEvaluation"]["relativeTolerance"], 0.005)
        self.assertEqual(answer["stockEvaluation"]["priceType"], "yahoo_historical_close")
        self.assertNotIn("stockEvaluation", public)
        self.assertEqual(public["prompt"], answer["prompt"])
        params = request.call_args.kwargs["params"]
        self.assertEqual(params["period1"], stamp("2026-09-01T00:00:00Z"))
        self.assertEqual(params["period2"], stamp("2026-10-01T00:00:00Z"))
        self.assertNotIn("range", params)
        self.assertIn("goldUrls", answer)
        self.assertEqual(answer["_provenance"]["referenceAsOf"], self.window.cutoff_text)
        with patch.object(curator, "request_json", return_value=payload):
            midnight_window = HistoricalWindow("2026-10-01T00:00:00Z", "2026-09")
            service = HistoricalCollector(SimpleNamespace(**vars(curator)), midnight_window)
            _, boundary_answer = service.yahoo(object(), "Apple", "AAPL", 1, "finance_sec")
        self.assertEqual(boundary_answer["stockEvaluation"]["date"], "2026-09-30")
        self.assertEqual(boundary_answer["stockEvaluation"]["expectedPrice"], 100.25)

    def test_stackoverflow_excludes_unanswered_future_and_mutated_answers(self):
        common = {
            "title": "How to fix this?",
            "body": "Example failing code",
            "creation_date": stamp("2026-09-02T00:00:00Z"),
            "last_activity_date": stamp("2026-09-10T00:00:00Z"),
        }
        questions = {
            "items": [
                dict(common, question_id=1, answer_count=0),
                dict(
                    common,
                    question_id=2,
                    answer_count=2,
                    link="https://stackoverflow.com/questions/2/example",
                ),
                dict(
                    common,
                    question_id=3,
                    answer_count=1,
                    link="https://stackoverflow.com/questions/3/example",
                ),
            ],
            "has_more": False,
        }
        answers = {
            "items": [
                {
                    "answer_id": 20,
                    "body": "Future answer " * 10,
                    "creation_date": stamp("2026-10-01T00:00:00Z"),
                    "score": 20,
                },
                {
                    "answer_id": 21,
                    "body": "Post-cutoff edit " * 10,
                    "creation_date": stamp("2026-09-02T00:00:00Z"),
                    "last_edit_date": stamp("2026-10-01T00:00:00Z"),
                    "score": 10,
                },
            ]
        }
        good = {
            "items": [
                {
                    "answer_id": 30,
                    "body": "A substantive and correct-looking explanation with code details " * 2,
                    "creation_date": stamp("2026-09-04T00:00:00Z"),
                    "score": 1,
                }
            ]
        }
        with patch.object(
            curator, "request_json", side_effect=[questions, answers, good]
        ) as request:
            service = HistoricalCollector(SimpleNamespace(**vars(curator)), self.window)
            rows = service.stackoverflow(object(), 1, "coding_debugging")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["_provenance"]["sourceRecordId"], "3")
        self.assertEqual(request.call_count, 3)
        self.assertNotIn("No answer", rows[0][1]["answer"])
        self.assertIn(self.window.cutoff_text, rows[0][0]["prompt"])
        with patch.object(
            curator,
            "request_json",
            return_value={"items": [dict(common, question_id=1, answer_count=0)]},
        ):
            service = HistoricalCollector(SimpleNamespace(**vars(curator)), self.window)
            with self.assertRaisesRegex(RuntimeError, "substantive pre-cutoff"):
                service.stackoverflow(object(), 1, "coding_debugging")

    def test_unsupported_mutable_sources_fail_without_current_network_calls(self):
        with (
            patch.object(curator, "request_json") as request,
            patch.object(curator, "request_text") as text,
        ):
            for source in (
                "ats_job_postings_live",
                "wikidata_products_pricing",
                "brand_socials",
                "freshqa_fast_changing",
            ):
                with (
                    self.subTest(source=source),
                    self.assertRaisesRegex(RuntimeError, "will not be backdated"),
                ):
                    curator.collect(
                        object(),
                        {"sourceCategory": source, "domain": "synthetic", "expectedCases": 1},
                    )
            request.assert_not_called()
            text.assert_not_called()

    def test_preflight_reports_all_missing_snapshots_before_network_or_output_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "expectedCases": 5,
                        "sources": [
                            {
                                "sourceCategory": "wikidata_products_pricing",
                                "domain": "synthetic",
                                "expectedCases": 2,
                            },
                            {
                                "sourceCategory": "ats_job_postings_live",
                                "domain": "synthetic",
                                "expectedCases": 3,
                            },
                        ],
                    }
                )
            )
            output = root / "output.jsonl"
            output.write_text("unchanged")
            with (
                patch.object(
                    curator.sys,
                    "argv",
                    [
                        str(SCRIPT),
                        "--manifest",
                        str(manifest),
                        "--output",
                        str(output),
                        "--as-of",
                        "2026-10-17",
                    ],
                ),
                patch.object(curator.httpx, "Client") as client,
                redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as failure,
            ):
                curator.main()
            self.assertIn("wikidata_products_pricing: 2", str(failure.exception))
            self.assertIn("ats_job_postings_live: 3", str(failure.exception))
            client.assert_not_called()
            self.assertEqual(output.read_text(), "unchanged")

    def test_wikipedia_only_dated_description_leaf_events_not_navigation(self):
        body = """<ul><li>Today's most viewed articles should never become event data.
        </li></ul>
        <div id="2026_September_30" class="current-events-main vevent">
          <div class="current-events-content description"><ul><li>Conflict category<ul>
            <li>A sufficiently detailed event involving two countries is reported on the target day.
            </li></ul></li></ul></div>
          <ul><li>Sidebar inside the day box is also unrelated navigation text.
          This must be excluded.</li></ul>
        </div><ul><li>Footer navigation after the last daily box must never inherit its date.
        </li></ul>"""
        payloads = [
            {
                "query": {
                    "pages": [{"revisions": [{"revid": 123, "timestamp": "2026-09-30T20:00:00Z"}]}]
                }
            },
            {"parse": {"text": body}},
        ]
        with patch.object(curator, "request_json", side_effect=payloads):
            service = HistoricalCollector(SimpleNamespace(**vars(curator)), self.window)
            rows = service.wikipedia(object(), 1, "breaking_news_freshness")
        self.assertIn("two countries", rows[0][1]["answer"])
        self.assertNotIn("navigation", rows[0][1]["answer"])
        self.assertEqual(rows[0][1]["goldUrls"], ["https://en.wikipedia.org/w/index.php?oldid=123"])

    def test_historical_snapshot_requires_cutoff_capture_and_evidence_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "historical.json"
            evidence.write_text('{"actualArchivedContent":"synthetic pricing"}')
            record = {
                "sourceCategory": "wikidata_products_pricing",
                "prompt": "What was the price?",
                "answer": "USD 10",
                "sourceName": "Archived vendor pricing",
                "sourceUrl": "https://archive.example/pricing/20260930",
                "sourceRecordId": "synthetic-1",
                "referenceAsOf": "2026-09-30T20:00:00Z",
                "evidenceCapturedAt": "2026-09-30T20:00:00Z",
                "evidencePath": "historical.json",
                "evidenceSha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }
            snapshot = root / "snapshots.jsonl"
            snapshot.write_text(json.dumps(record) + "\n")
            self.assertEqual(
                len(load_snapshots(snapshot, self.window)[record["sourceCategory"]]), 1
            )
            record["evidenceCapturedAt"] = "2026-10-01T00:00:00Z"
            snapshot.write_text(json.dumps(record) + "\n")
            with self.assertRaisesRegex(ValueError, "captured in target month"):
                load_snapshots(snapshot, self.window)
            record["evidenceCapturedAt"] = "2026-09-30T20:00:00Z"
            record["evidenceSha256"] = "0" * 64
            snapshot.write_text(json.dumps(record) + "\n")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                load_snapshots(snapshot, self.window)
            for bad_path, reason in (
                ("../escape.json", "remain inside"),
                (".env.json", "credential paths"),
            ):
                record["evidencePath"] = bad_path
                snapshot.write_text(json.dumps(record) + "\n")
                with (
                    patch.object(Path, "read_bytes") as read,
                    self.assertRaisesRegex(ValueError, reason),
                ):
                    load_snapshots(snapshot, self.window)
                read.assert_not_called()

    def test_snapshot_symlink_to_credential_target_is_rejected_before_file_access(self):
        # Resolve is mocked: no credential file or symlink is created or inspected.
        for target in (Path("synthetic-only/.env"), Path("synthetic-only/.env/snapshots.jsonl")):
            with (
                self.subTest(target=str(target)),
                patch.object(Path, "resolve", return_value=target),
                patch.object(Path, "stat") as stat,
                patch.object(Path, "read_text") as read,
                self.assertRaisesRegex(ValueError, "Resolved historical snapshots"),
            ):
                load_snapshots(Path("synthetic-only/snapshots.jsonl"), self.window)
            stat.assert_not_called()
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
