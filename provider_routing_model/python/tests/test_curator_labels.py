"""Offline regression checks for source labeling and matched curator outputs."""

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/curate-provider-eval-585.py"
SPEC = importlib.util.spec_from_file_location("curator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
curator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(curator)

SOURCES = {
    "stackoverflow_api_live": ("Stack Exchange API", "https://stackoverflow.com/questions/1/test"),
    "github_issues_live": ("GitHub Issues API", "https://github.com/example/repo/issues/1"),
    "techfresh": ("PyPI project JSON", "https://pypi.org/project/example/"),
}


def source_spec(category):
    return {"sourceCategory": category, "domain": "coding_debugging", "expectedCases": 1}


def sample(category):
    name, url = SOURCES[category]
    return curator.case(
        category,
        "coding_debugging",
        1,
        f"Synthetic {category} question",
        "Synthetic answer",
        name,
        url,
        "source-1",
        "2026-10-17",
    )


class CuratorLabelTests(unittest.TestCase):
    def test_source_identity_rejects_the_original_three_way_rotation(self):
        categories = list(SOURCES)
        for index, category in enumerate(categories):
            with self.subTest(category=category):
                curator.validate_source_rows(source_spec(category), [sample(category)])
                other_name, other_url = SOURCES[categories[(index + 1) % 3]]
                with self.assertRaises(ValueError):
                    curator.case(
                        category,
                        "coding_debugging",
                        1,
                        "Synthetic",
                        "Synthetic",
                        other_name,
                        other_url,
                        "1",
                        "2026-10-17",
                    )
        with self.assertRaises(ValueError):
            curator.validate_source_identity(
                "techfresh", "PyPI project JSON", "https://pypi.org.example.test/project/example/"
            )
        with self.assertRaises(ValueError):
            curator.validate_source_identity(
                "techfresh", "GitHub Issues API", "https://pypi.org/project/example/"
            )

    def test_manifest_labels_and_public_answer_provenance_joins_are_checked(self):
        category = "techfresh"
        mutations = [
            lambda p, a: p.update(domain="finance_sec"),
            lambda p, a: a.update(id="different-case"),
            lambda p, a: a.update(prompt="different-question"),
            lambda p, a: a["_provenance"].update(id="different-case"),
            lambda p, a: a["_provenance"].update(sourceCategory="github_issues_live"),
            lambda p, a: a["_provenance"].update(sourceUrl="https://github.com/example/repo"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                public, answer = sample(category)
                mutate(public, answer)
                with self.assertRaises(ValueError):
                    curator.validate_source_rows(source_spec(category), [(public, answer)])

    def run_collection(self, folder, swapped):
        categories = list(SOURCES)
        manifest = folder / "manifest.json"
        manifest.write_text(
            json.dumps({"expectedCases": 3, "sources": [source_spec(c) for c in categories]})
        )
        paths = [folder / name for name in ("inputs.jsonl", "answers.jsonl", "provenance.jsonl")]
        argv = [
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--output",
            str(paths[0]),
            "--answers",
            str(paths[1]),
            "--provenance",
            str(paths[2]),
        ]

        def collect(_client, spec):
            category = spec["sourceCategory"]
            if swapped:
                category = categories[(categories.index(category) + 1) % 3]
            return [sample(category)]

        with (
            patch.object(curator, "collect", side_effect=collect),
            patch.object(curator.httpx, "Client") as client,
            patch.object(curator.os, "getenv", return_value="synthetic-github-token"),
            patch.object(curator.sys, "argv", argv),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            curator.main()
            self.assertNotIn("Authorization", client.call_args.kwargs["headers"])
        return paths

    def test_github_auth_is_attached_to_github_requests_only(self):
        payload = {
            "items": [
                {
                    "html_url": SOURCES["github_issues_live"][1],
                    "repository_url": "https://api.github.com/repos/example/repo",
                    "number": 1,
                    "title": "Synthetic issue",
                    "state": "closed",
                    "created_at": "2026-09-01T12:00:00Z",
                    "closed_at": "2026-09-02T12:00:00Z",
                    "updated_at": "2026-09-02T12:00:00Z",
                }
            ]
        }
        with (
            patch.object(curator.os, "getenv", return_value="synthetic-github-token"),
            patch.object(curator, "request_json", return_value=payload) as request,
            patch.object(curator, "WINDOW", curator.HistoricalWindow("2026-10-17")),
        ):
            curator.fetch_github(object(), 1, "coding_debugging")
        self.assertEqual(request.call_args.args[1], "https://api.github.com/search/issues")
        self.assertEqual(
            request.call_args.kwargs["headers"]["Authorization"], "Bearer synthetic-github-token"
        )

    def test_swapped_batches_keep_counts_but_fail_before_overwriting_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for name in ("inputs.jsonl", "answers.jsonl", "provenance.jsonl"):
                (folder / name).write_text("existing-artifact")
            with self.assertRaisesRegex(SystemExit, "no output written"):
                self.run_collection(folder, swapped=True)
            for name in ("inputs.jsonl", "answers.jsonl", "provenance.jsonl"):
                self.assertEqual((folder / name).read_text(), "existing-artifact")

    def test_valid_collection_writes_matching_inputs_answers_and_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.run_collection(Path(temporary), swapped=False)
            inputs, answers, provenance = [
                [json.loads(line) for line in path.read_text().splitlines()] for path in paths
            ]
            self.assertEqual(len(inputs), 3)
            for public, answer, source in zip(inputs, answers, provenance, strict=True):
                self.assertEqual(public["id"], answer["id"])
                self.assertEqual(public["prompt"], answer["prompt"])
                self.assertEqual(public["id"], source["id"])
                self.assertEqual(public["sourceCategory"], source["sourceCategory"])
                self.assertNotIn("answer", public)
                self.assertNotIn("_provenance", answer)


if __name__ == "__main__":
    unittest.main()
