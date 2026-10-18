"""Focused source extraction and offline artifact checks for code API cases."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import ClassVar
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from pydantic import ValidationError

PYTHON_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(PYTHON_SRC))

from query_gold.categories import (  # noqa: E402
    code_api,
    code_api_paths,
)
from query_gold.models import QueryGoldCase  # noqa: E402

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CATEGORY_ARTIFACTS = (
    REPOSITORY_ROOT
    / "results"
    / "query-gold-curation"
    / "first-five-v1"
    / "categories"
    / code_api.CATEGORY_ID
)


class RstExtractionTests(unittest.TestCase):
    def test_signature_and_default_are_literal_directive_content(self):
        source = """.. function:: transform(value, count=2, *, strict=False)

   Documentation follows.
"""
        signature, excerpt = code_api._directive_signature(source, "transform")
        self.assertEqual(signature, "transform(value, count=2, *, strict=False)")
        self.assertEqual(excerpt, ".. function:: transform(value, count=2, *, strict=False)\n")
        self.assertIn(excerpt, source)
        self.assertEqual(code_api._default_from_signature(signature, "strict"), "False")
        self.assertEqual(code_api._default_from_signature(signature, "count"), "2")

    def test_wrong_documented_field_fails_instead_of_returning_an_adjacent_default(self):
        source = """.. function:: transform(value, count=2, *, strict=False)
"""
        signature, _ = code_api._directive_signature(source, "transform")
        with self.assertRaisesRegex(ValueError, "default not found"):
            code_api._default_from_signature(signature, "limit")
        with self.assertRaisesRegex(ValueError, "directive not found"):
            code_api._directive_signature(source, "transforms")

    def test_optional_rst_syntax_does_not_confuse_top_level_parameters(self):
        signature = "defaultdict(default_factory=None, /, [...])"
        self.assertEqual(code_api._default_from_signature(signature, "default_factory"), "None")

    def test_paragraph_excerpt_is_exact_and_does_not_absorb_the_next_bullet(self):
        source = (
            "Intro.\n\n"
            "* The `old_callback` parameter is deprecated when `new_callback` is added.\n"
            "  Use an exception instance.\n\n"
            "* A separate change follows.\n"
        )
        excerpt = code_api._paragraph_excerpt(source, "old_callback")
        self.assertEqual(
            excerpt,
            "* The `old_callback` parameter is deprecated when `new_callback` is added.\n"
            "  Use an exception instance.\n",
        )
        self.assertIn(excerpt, source)
        self.assertNotIn("separate change", excerpt)

    def test_release_excerpt_keeps_the_exact_version_heading(self):
        source = (
            "Version 8.1.7\n----------\n\n"
            "Released 2023-08-17\n\n"
            "- A separate fix.\n"
            "- Fix issue with completion script for Fish shell.\n\n"
            "Version 8.1.6\n----------\n"
            "- Another completion fix.\n"
        )
        excerpt = code_api.release_section_excerpt(
            source, "8.1.7", "Fix issue with completion script"
        )
        self.assertIn("Version 8.1.7", excerpt)
        self.assertIn("Fish shell", excerpt)
        self.assertNotIn("Version 8.1.6", excerpt)
        self.assertIn(excerpt, source)


class PythonAndClickExtractionTests(unittest.TestCase):
    def test_python_default_is_taken_from_the_named_class_and_method(self):
        source = """class Table:
    def combine(self, how='inner', *, sort=False):
        return how

    def drop(self, how=None):
        return how
"""
        answer, excerpt, value = code_api._python_default(source, "Table.combine", "sort")
        self.assertEqual(answer, "False")
        self.assertIs(value, False)
        self.assertIn("def combine(self, how='inner', *, sort=False):", excerpt)
        self.assertIn(excerpt, source)
        self.assertEqual(code_api._python_default(source, "Table.drop", "how")[0], "None")

    def test_wrong_python_class_or_parameter_is_rejected(self):
        source = """class Table:
    def combine(self, how='inner'):
        return how
"""
        with self.assertRaisesRegex(ValueError, "class not found"):
            code_api._python_default(source, "Frame.combine", "how")
        with self.assertRaisesRegex(ValueError, "default not found"):
            code_api._python_default(source, "Table.combine", "axis")

    def test_click_flag_and_numeric_default_are_parsed_from_one_answer_line(self):
        option_line = "    @click.option('-v', '--verbose', count=True)\n"
        self.assertEqual(code_api.long_option(option_line), "--verbose")
        port_line = "    @click.option('--port', default=8000)\n"
        expression, value = code_api._click_default(port_line, "default")
        self.assertEqual(expression, "8000")
        self.assertEqual(value, 8000)
        with self.assertRaisesRegex(ValueError, "no long-form"):
            code_api.long_option("@click.option('-v', count=True)\n")

    def test_click_section_excerpt_retains_heading_and_full_example_context(self):
        source = (
            "Counting\n--------\n\n"
            "Repeat options to increase a count.\n\n"
            ".. click:example::\n\n"
            "    @click.option('-v', '--verbose', count=True)\n"
            "    def log(verbose):\n        pass\n\n"
            "Next Section\n------------\n\nBody.\n"
        )
        excerpt = code_api.section_option_excerpt(
            source, "Counting", "@click.option('-v', '--verbose', count=True)"
        )
        self.assertIn("Counting\n--------", excerpt)
        self.assertIn("def log(verbose):", excerpt)
        self.assertIn(excerpt, source)
        self.assertNotIn("Next Section", excerpt)

    def test_click_command_default_keeps_option_and_command_context(self):
        source = (
            "    @cli.command()\n"
            "    @click.option('--port', default=8000)\n"
            "    def runserver(port):\n"
            "        click.echo(port)\n"
        )
        answer, excerpt, value = code_api.click_command_default(
            source, "runserver", "--port", code_api._click_default
        )
        self.assertEqual(answer, "8000")
        self.assertEqual(value, 8000)
        self.assertIn("--port", excerpt)
        self.assertIn("def runserver(port):", excerpt)
        self.assertIn(excerpt, source)

    def test_units_are_required_and_field_specific(self):
        arity = next(
            spec
            for spec in code_api.FACT_SPECS
            if spec.id == "code_api_click_parameter_option_arity"
        )
        code_api._validate_spec(arity)
        with self.assertRaisesRegex(ValueError, "units are invalid"):
            code_api._validate_spec(replace(arity, units="seconds"))

        port = next(
            spec
            for spec in code_api.FACT_SPECS
            if spec.id == "code_api_click_runserver_port_default"
        )
        code_api._validate_spec(port)
        with self.assertRaisesRegex(ValueError, "units are invalid"):
            code_api._validate_spec(replace(port, units="option value"))

        signature = next(
            spec for spec in code_api.FACT_SPECS if spec.question_type == "api_signature"
        )
        with self.assertRaisesRegex(ValueError, "units are not defined"):
            code_api._validate_spec(replace(signature, units="seconds"))


class QueryScopeAndDirectnessTests(unittest.TestCase):
    def _valid_record(self) -> dict[str, object]:
        return {
            "schemaVersion": "query-gold/v1",
            "id": "code_api_fixture_version",
            "categoryId": code_api.CATEGORY_ID,
            "query": "In pandas 2.2.3, what default does Table.combine specify?",
            "temporal": {"kind": "version", "precision": "version", "version": "2.2.3"},
            "gold": {"answer": "False", "acceptedAnswers": ["False"], "value": False},
            "evidence": [
                {
                    "url": "https://github.com/pandas-dev/pandas/blob/abc123/file.py",
                    "title": "pandas pinned source",
                    "retrievedAtUTC": "2026-10-17T12:00:00Z",
                    "sourceRecordId": "pandas-dev/pandas:file.py",
                    "upstreamRevision": "abc123",
                    "license": "BSD 3-Clause License",
                    "rawSha256": "0" * 64,
                    "rawPath": "raw/pandas/file.py",
                    "excerpt": "def combine(self, sort=False):",
                }
            ],
            "derivation": {
                "sourceFamily": "official_pandas_source",
                "generatorVersion": "query-gold/v1",
                "questionType": "parameter_default",
            },
        }

    def test_mismatched_date_fields_and_precision_fail_strict_temporal_validation(self):
        record = self._valid_record()
        with_extra_date = copy.deepcopy(record)
        with_extra_date["temporal"]["date"] = "2024-02-29"  # type: ignore[index]
        with self.assertRaises(ValidationError):
            QueryGoldCase.model_validate(with_extra_date)

        wrong_precision = copy.deepcopy(record)
        wrong_precision["temporal"]["precision"] = "day"  # type: ignore[index]
        with self.assertRaises(ValidationError):
            QueryGoldCase.model_validate(wrong_precision)

    def test_directness_check_rejects_vague_latest_derived_and_compound_prompts(self):
        bad_queries = (
            "What is the latest value?",
            "Calculate the total for pandas 2.2.3?",
            "What is the default, and which method replaces it?",
            "What is the default in the above source for pandas 2.2.3?",
        )
        for query in bad_queries:
            with self.subTest(query=query), self.assertRaises(ValueError):
                code_api._assert_query_direct(query, "2.2.3", "fixture")

    def test_strict_case_schema_keeps_version_and_units_in_their_declared_fields(self):
        record = self._valid_record()
        parsed = QueryGoldCase.model_validate(record)
        self.assertEqual(parsed.temporal.version, "2.2.3")
        self.assertIsNone(parsed.gold.units)

        unknown = copy.deepcopy(record)
        unknown["gold"]["unit"] = "rows"  # type: ignore[index]
        with self.assertRaises(ValidationError):
            QueryGoldCase.model_validate(unknown)


class OfflineArtifactIntegrationTests(unittest.TestCase):
    def test_collects_and_verifies_all_50_cases_without_http(self):
        manifest = CATEGORY_ARTIFACTS / "raw" / "snapshot_manifest.json"
        if not manifest.is_file():
            self.skipTest("private pinned-source cache is absent in this checkout")

        with patch.object(
            code_api,
            "open_without_redirects",
            side_effect=AssertionError("cache miss caused HTTP"),
        ):
            records = code_api.collect(CATEGORY_ARTIFACTS, 50)

        self.assertEqual(len(records), 50)
        self.assertEqual(len({record["id"] for record in records}), 50)
        self.assertGreaterEqual(
            len({record["evidence"][0]["sourceRecordId"] for record in records}), 25
        )
        self.assertGreaterEqual(
            len({record["derivation"]["questionType"] for record in records}), 3
        )
        for record in records:
            evidence = record["evidence"][0]
            payload = (CATEGORY_ARTIFACTS / evidence["rawPath"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), evidence["rawSha256"])
            self.assertIn(evidence["excerpt"].encode("utf-8"), payload)
            self.assertIn(record["temporal"]["version"], record["query"])
            self.assertIn("/blob/", evidence["url"])

        expected_click_gold = {
            "code_api_click_count_flag": ("--verbose", "Counting"),
            "code_api_click_repeated_value_flag": ("--message", "Multiple Options"),
            "code_api_click_file_input_long_flag": (
                "--input",
                "Multi Command Pipelines",
            ),
        }
        by_id = {record["id"]: record for record in records}
        for case_id, (answer, heading) in expected_click_gold.items():
            with self.subTest(case_id=case_id):
                record = by_id[case_id]
                self.assertEqual(record["gold"]["answer"], answer)
                self.assertIn(heading, record["evidence"][0]["excerpt"])
                self.assertGreater(len(record["evidence"][0]["excerpt"]), 150)

        pandas_date_format = by_id["code_api_pd_to_json_date_format_default"]
        self.assertIn("internal `pandas.io.json._json.to_json`", pandas_date_format["query"])
        self.assertEqual(pandas_date_format["gold"]["value"], "epoch")

        jsonl = (CATEGORY_ARTIFACTS / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(jsonl), 50)


class BoundedRequestTests(unittest.TestCase):
    def test_absolute_path_guard_rejects_windows_ads_before_filesystem_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            alternate_stream_path = Path(temporary) / "snapshot.json:alternate"
            with self.assertRaisesRegex(ValueError, "not portable to Windows"):
                code_api_paths.guard_absolute_path(alternate_stream_path)
            self.assertFalse((Path(temporary) / "snapshot.json").exists())

    def test_redirect_fails_closed_without_following_the_second_hop(self):
        class RedirectHandler(BaseHTTPRequestHandler):
            paths: ClassVar[list[str]] = []

            def do_GET(self):
                type(self).paths.append(self.path)
                self.send_response(302 if self.path == "/start" else 200)
                if self.path == "/start":
                    self.send_header("Location", "/target")
                self.end_headers()

            def log_message(self, format, *args):
                return

        RedirectHandler.paths.clear()
        server = HTTPServer(("127.0.0.1", 0), RedirectHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/start"
            with self.assertRaises(HTTPError) as caught:
                code_api.open_without_redirects(Request(url), timeout=1)
            self.assertEqual(caught.exception.code, 302)
            self.assertEqual(RedirectHandler.paths, ["/start"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
        self.assertFalse(thread.is_alive())

    def test_retry_success_keeps_both_durable_attempt_outcomes(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self, limit: int) -> bytes:
                return b"pinned source bytes"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "raw" / "snapshot_manifest.json"
            manifest = {
                "sources": [],
                "failures": [],
                "physicalRequestsBudgetConsumed": 0,
                "physicalRequestsThisCollection": 0,
            }
            count = [0]
            with patch.object(
                code_api,
                "open_without_redirects",
                side_effect=[URLError("temporary failure"), Response()],
            ):
                code_api._fetch_pinned_source(
                    "python/cpython:Doc/library/os.rst",
                    request_count=count,
                    manifest=manifest,
                    manifest_path=manifest_path,
                    root=root,
                )

            ledger = root / "raw" / "request_attempts.jsonl"
            events = [json.loads(line) for line in ledger.read_text().splitlines()]
            self.assertEqual(code_api.count_started_attempts(ledger), 2)
            self.assertEqual(
                [event["event"] for event in events],
                ["started", "finished", "started", "finished"],
            )
            self.assertEqual(events[1]["outcome"], "transport_error")
            self.assertEqual(events[1]["error"], "URLError")
            self.assertEqual(events[3]["outcome"], "success")
            self.assertEqual(events[3]["statusCode"], 200)
            self.assertEqual(manifest["physicalRequestsBudgetConsumed"], 2)
            self.assertEqual(manifest["physicalRequestsThisCollection"], 2)

    def test_missing_source_with_ambiguous_legacy_budget_fails_without_http(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "raw" / "snapshot_manifest.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "query-gold-source-snapshots/v1",
                        "sources": [],
                        "failures": [],
                        "physicalRequestsBudgetConsumed": 39,
                        "requestAccounting": {
                            "physicalRequestsLowerBound": 35,
                            "physicalRequestsUpperBound": 39,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(
                    code_api,
                    "open_without_redirects",
                    side_effect=AssertionError("unknown historical budget must block HTTP"),
                ),
                self.assertRaisesRegex(RuntimeError, "redirect hops are unknown"),
            ):
                code_api.collect(root, 1)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["historicalRedirectHopsUnknown"])
            self.assertEqual(manifest["physicalRequestsBudgetConsumed"], 39)
            self.assertFalse((root / "raw" / "request_attempts.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
