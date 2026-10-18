"""Command-line interface for preparing BrowseComp benchmarks."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Literal

from browse_comp.prepare import prepare_benchmark_artifacts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="prepare-browse-comp",
        description="Prepare BrowseComp benchmark datasets and answer sets for provider evals.",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Local file path or URL to BrowseComp parquet dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Target directory to write JSONL artifacts (defaults to repo data/).",
    )
    parser.add_argument(
        "--subset-size",
        type=int,
        default=10,
        help="Number of questions in subset benchmark (default: 10).",
    )
    parser.add_argument(
        "--required-tools",
        nargs="*",
        choices=["search", "fetch"],
        default=None,
        help="Optional tool names required for each case (e.g. --required-tools search fetch).",
    )
    parser.add_argument(
        "--id-prefix",
        type=str,
        default="browse-comp-",
        help="Prefix for benchmark case IDs (default: browse-comp-).",
    )
    parser.add_argument(
        "--copy-to-benchmarks",
        action="store_true",
        default=True,
        help="Also place a copy of benchmark inputs under benchmarks/inputs/ and answers under "
        "benchmarks/answers/ (gitignored).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    args = parse_args(argv)

    tools: list[Literal["search", "fetch"]] | None = None
    if args.required_tools:
        tools = [t for t in args.required_tools if t in ("search", "fetch")]

    print("Fetching and processing BrowseComp dataset...")
    artifacts = prepare_benchmark_artifacts(
        source=args.source,
        output_dir=args.output_dir,
        subset_size=args.subset_size,
        required_tools=tools,
        id_prefix=args.id_prefix,
    )

    print("\nSuccessfully generated artifacts:")
    for name, path in artifacts.items():
        print(f"  - {name}: {path}")

    if args.copy_to_benchmarks:
        repo_root = Path(__file__).resolve().parents[3]
        bench_inputs = repo_root / "benchmarks" / "inputs"
        bench_answers = repo_root / "benchmarks" / "answers"
        bench_inputs.mkdir(parents=True, exist_ok=True)
        bench_answers.mkdir(parents=True, exist_ok=True)

        target_full_input = bench_inputs / "browse_comp.jsonl"
        target_subset_input = bench_inputs / f"browse_comp_subset{args.subset_size}.jsonl"
        target_full_answers = bench_answers / "browse_comp_answers.jsonl"
        target_subset_answers = (
            bench_answers / f"browse_comp_subset{args.subset_size}_answers.jsonl"
        )

        shutil.copyfile(artifacts["full_inputs"], target_full_input)
        shutil.copyfile(artifacts["subset_inputs"], target_subset_input)
        shutil.copyfile(artifacts["full_answers"], target_full_answers)
        shutil.copyfile(artifacts["subset_answers"], target_subset_answers)

        print("\nAlso mirrored to benchmarks/ directory (gitignored):")
        print(f"  - Inputs: {target_full_input}")
        print(f"  - Subset inputs: {target_subset_input}")
        print(f"  - Answers: {target_full_answers}")
        print(f"  - Subset answers: {target_subset_answers}")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
