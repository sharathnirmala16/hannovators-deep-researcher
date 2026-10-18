"""Offline assembly/export and failed-run preservation tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from query_gold_test_helpers import make_case, make_cases

from query_gold.io import read_jsonl
from query_gold.pipeline import (
    DatasetFailure,
    assemble_dataset,
    collect_categories,
    export_dataset,
)
from query_gold.validation import CATEGORY_IDS, ValidationPolicy


def policy() -> ValidationPolicy:
    return ValidationPolicy(
        expected_count_per_category=5,
        min_distinct_source_ids=5,
        min_question_types=3,
    )


class QueryGoldPipelineTests(unittest.TestCase):
    def prepare(self, root: Path) -> None:
        make_cases(root, count_per_category=5)
        assemble_dataset(root, policy=policy())

    @unittest.skipUnless(os.name == "nt", "Windows case-insensitive path regression")
    def test_export_rejects_case_aliases_before_writing_any_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            public = folder / "QueryGold.jsonl"
            private = folder / "querygold.jsonl"
            with self.assertRaisesRegex(ValueError, "overlap"):
                export_dataset(folder / "artifacts", public_path=public, private_path=private)
            self.assertFalse(public.exists())

    def test_export_destinations_cannot_overwrite_private_artifacts_or_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            root = folder / "artifacts"
            private = folder / "private.jsonl"
            reserved_paths = (
                root / "cases.jsonl",
                root / "manifest.json",
                root / "query-gold-v1.schema.json",
                root / "validation-report.json",
                root / "rejection-report.json",
                root / "collection-state.json",
                root / "jev-cache.json",
                root / "categories" / CATEGORY_IDS[0] / "cases.jsonl",
                root / "jev-reports" / "review.json",
            )
            for public in reserved_paths:
                with (
                    self.subTest(public=public),
                    self.assertRaisesRegex(ValueError, "private artifact root"),
                ):
                    export_dataset(root, public_path=public, private_path=private)
                self.assertFalse(public.exists())

    def test_canonical_assembly_and_public_private_exports_have_exact_separation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "artifacts"
            self.prepare(root)
            public = Path(temporary) / "public.jsonl"
            private = Path(temporary) / "private.jsonl"
            exported = export_dataset(
                root, public_path=public, private_path=private, policy=policy()
            )

            public_rows = read_jsonl(public)
            private_rows = read_jsonl(private)
            self.assertEqual(exported.case_count, 5 * len(policy().categories))
            self.assertEqual(len(public_rows), len(private_rows))
            self.assertEqual(set(public_rows[0]), {"id", "prompt"})
            self.assertEqual(set(private_rows[0]), {"id", "prompt", "answer", "goldUrls"})
            for public_row, private_row in zip(public_rows, private_rows, strict=True):
                self.assertEqual(public_row["id"], private_row["id"])
                self.assertEqual(public_row["prompt"], private_row["prompt"])
                self.assertNotIn("answer", public_row)
                self.assertNotIn("goldUrls", public_row)
                self.assertTrue(private_row["goldUrls"])

    def test_default_exports_use_eval_v2_question_and_answer_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            root = repo_root / "artifacts"
            self.prepare(root)

            with patch("query_gold.pipeline.repository_root", return_value=repo_root):
                exported = export_dataset(root, policy=policy())

            expected_public = repo_root / "benchmarks/eval_v2/questions/query_gold.jsonl"
            expected_private = repo_root / "benchmarks/eval_v2/answers/query_gold_answers.jsonl"
            self.assertEqual(exported.public_path, expected_public)
            self.assertEqual(exported.private_path, expected_private)
            self.assertTrue(expected_public.is_file())
            self.assertTrue(expected_private.is_file())
            self.assertFalse(expected_public.is_relative_to(root))
            self.assertFalse(expected_private.is_relative_to(root))

    def test_failed_assembly_does_not_replace_previous_canonical_or_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            root = folder / "artifacts"
            self.prepare(root)
            public = folder / "public.jsonl"
            private = folder / "private.jsonl"
            export_dataset(root, public_path=public, private_path=private, policy=policy())
            canonical_before = (root / "cases.jsonl").read_bytes()
            public_before = public.read_bytes()
            private_before = private.read_bytes()

            cache = root / "categories" / CATEGORY_IDS[0] / "cases.jsonl"
            rows = read_jsonl(cache)
            rows[0]["query"] = "Using the above document, calculate the company's revenue."
            from query_gold.io import atomic_write_jsonl

            atomic_write_jsonl(cache, rows)
            with self.assertRaisesRegex(
                DatasetFailure, "canonical dataset and exports were not replaced"
            ):
                assemble_dataset(root, policy=policy())

            self.assertEqual((root / "cases.jsonl").read_bytes(), canonical_before)
            self.assertEqual(public.read_bytes(), public_before)
            self.assertEqual(private.read_bytes(), private_before)

    def test_cached_category_records_are_reused_without_importing_collectors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_cases(root, count_per_category=5, categories=(CATEGORY_IDS[0],))
            with patch("query_gold.pipeline.importlib.import_module") as importer:
                rows = collect_categories(
                    root,
                    count=5,
                    categories=(CATEGORY_IDS[0],),
                    min_distinct_source_ids=5,
                    min_question_types=3,
                )
            importer.assert_not_called()
            self.assertEqual(len(rows[CATEGORY_IDS[0]]), 5)
            self.assertTrue((root / "collection-state.json").is_file())

    def test_refresh_invokes_factory_and_failed_refresh_preserves_valid_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            root = folder / "artifacts"
            self.prepare(root)
            public = folder / "public.jsonl"
            private = folder / "private.jsonl"
            export_dataset(root, public_path=public, private_path=private, policy=policy())
            canonical_before = (root / "cases.jsonl").read_bytes()
            public_before = public.read_bytes()
            private_before = private.read_bytes()

            with (
                patch(
                    "query_gold.pipeline.importlib.import_module",
                    side_effect=RuntimeError("synthetic collector failure"),
                ),
                self.assertRaisesRegex(DatasetFailure, "Category collection failed"),
            ):
                collect_categories(
                    root,
                    count=5,
                    categories=(CATEGORY_IDS[0],),
                    refresh=True,
                    min_distinct_source_ids=5,
                    min_question_types=3,
                )
            self.assertEqual((root / "cases.jsonl").read_bytes(), canonical_before)
            self.assertEqual(public.read_bytes(), public_before)
            self.assertEqual(private.read_bytes(), private_before)

    def test_refresh_factory_receives_its_category_output_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            returned: list[Path] = []

            def factory(*, output_dir: Path, count: int):
                returned.append(output_dir)
                return [make_case(CATEGORY_IDS[0], index, output_dir) for index in range(count)]

            with patch(
                "query_gold.pipeline.importlib.import_module",
                return_value=SimpleNamespace(collect=factory),
            ):
                rows = collect_categories(
                    root,
                    count=5,
                    categories=(CATEGORY_IDS[0],),
                    refresh=True,
                    min_distinct_source_ids=5,
                    min_question_types=3,
                )
            self.assertEqual(returned, [root / "categories" / CATEGORY_IDS[0]])
            self.assertEqual(len(rows[CATEGORY_IDS[0]]), 5)
            self.assertTrue((returned[0] / "cases.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
