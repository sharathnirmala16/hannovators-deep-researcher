"""Command-line entry points for query/gold curation and optional Jev review."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from query_gold.io import jsonl_bytes, read_json, sha256_bytes
from query_gold.jev import (
    api_key_from_environment,
    run_jev_review,
    zero_data_retention_requested,
)
from query_gold.models import QueryGoldCase
from query_gold.pipeline import (
    DatasetFailure,
    assemble_dataset,
    collect_categories,
    default_artifact_root,
    export_dataset,
    load_canonical_cases,
    validate_category_dataset,
)
from query_gold.validation import CATEGORY_IDS, ValidationReport


def _root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=default_artifact_root(),
        help="Private artifact root (default: results/query-gold-curation/first-five-v1).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="query-gold",
        description="Curate, validate, assemble, and export the first-five query/gold dataset.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser(
        "collect", help="Reuse caches or explicitly collect categories."
    )
    _root_argument(collect_parser)
    collect_parser.add_argument(
        "--count", type=int, default=50, help="Cases per category (default: 50)."
    )
    collect_parser.add_argument(
        "--category",
        action="append",
        choices=CATEGORY_IDS,
        help="Collect one category; repeat to select more than one (default: all five).",
    )
    collect_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Explicitly call category collectors instead of reusing cases.jsonl caches.",
    )

    validate_parser = subparsers.add_parser(
        "validate", help="Validate cached category records and evidence."
    )
    _root_argument(validate_parser)

    assemble_parser = subparsers.add_parser(
        "assemble", help="Assemble valid category caches into private canonical artifacts."
    )
    _root_argument(assemble_parser)

    export_parser = subparsers.add_parser(
        "export", help="Write the exact public input and separate private answer join."
    )
    _root_argument(export_parser)
    export_parser.add_argument("--public-output", type=Path, default=None)
    export_parser.add_argument("--private-output", type=Path, default=None)

    jev_parser = subparsers.add_parser(
        "jev-review", help="Run the bounded CommandCode Jev reviewer (live calls are opt-in)."
    )
    _root_argument(jev_parser)
    jev_parser.add_argument(
        "--live-jevreview",
        action="store_true",
        help="Required explicit opt-in before any Jev network request.",
    )
    return parser


def _print_validation(report: ValidationReport) -> int:
    valid = report.valid
    cases = report.caseCount
    errors = report.errors
    warnings = report.warnings
    print(f"Cases: {cases}; errors: {len(errors)}; warnings: {len(warnings)}")
    if not valid:
        codes = sorted({issue.code for issue in errors})
        print("Validation failed: " + ", ".join(codes))
        return 1
    print("Validation passed.")
    return 0


def _validate_canonical_manifest(root: Path, cases: list[QueryGoldCase]) -> bool:
    try:
        manifest = read_json(root / "manifest.json")
    except (OSError, ValueError):
        return False
    if not isinstance(manifest, dict):
        return False
    return manifest.get("datasetSha256") == sha256_bytes(jsonl_bytes(cases))


def _run_collect(args: argparse.Namespace) -> int:
    categories = tuple(args.category or CATEGORY_IDS)
    collected = collect_categories(
        args.root,
        count=args.count,
        categories=categories,
        refresh=args.refresh,
    )
    total = sum(len(rows) for rows in collected.values())
    print(f"Collected or reused {total} records across {len(collected)} categories.")
    if categories == CATEGORY_IDS:
        artifacts = assemble_dataset(args.root, refresh_requested=args.refresh)
        print(f"Assembled {artifacts.case_count} cases; SHA-256 {artifacts.dataset_sha256}.")
    else:
        print("Partial category collection only; assemble after all five caches are available.")
    return 0


def _run_jev(args: argparse.Namespace) -> int:
    if not args.live_jevreview:
        print(
            "No Jev request made. Pass --live-jevreview to explicitly enable "
            "the bounded live reviewer."
        )
        return 2

    validation = validate_category_dataset(args.root)
    if not validation.valid:
        _print_validation(validation)
        print("Jev was not called because dataset validation failed.")
        return 1
    cases = load_canonical_cases(args.root)
    if validation.datasetSha256 != sha256_bytes(jsonl_bytes(cases)):
        print("Jev was not called because category caches and canonical cases differ.")
        return 1
    if not _validate_canonical_manifest(args.root, cases):
        print("Jev was not called because the canonical dataset does not match its manifest.")
        return 1

    if zero_data_retention_requested():
        report, report_path = run_jev_review(
            cases,
            args.root,
            api_key=None,
            zdr_requested=True,
        )
        print(
            "Jev review stopped with unsupported_zdr_requested; no requests were sent. "
            f"Private report: {report_path}"
        )
        return 2

    api_key = api_key_from_environment()
    if api_key is None:
        print("Live Jev review requires CMD_API_KEY or COMMANDCODE_API_KEY; no request was sent.")
        return 2

    report, report_path = run_jev_review(cases, args.root, api_key=api_key)
    sampled_count = report.get("reviewCoverage", {}).get("sampledCaseCount", 0)
    print(
        f"Jev status: {report['status']}; sampled: {sampled_count}; "
        f"physical requests: {report['physicalRequests']}; cache hits: {report['cacheHits']}."
    )
    print(f"Private Jev report: {report_path}")
    if report.get("calibration", {}).get("passed") is not True:
        print("Calibration did not pass; sampled records remain review_required.")
        return 1
    return 0


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            return _run_collect(args)
        if args.command == "validate":
            return _print_validation(validate_category_dataset(args.root))
        if args.command == "assemble":
            assembly_artifacts = assemble_dataset(args.root)
            print(
                f"Assembled {assembly_artifacts.case_count} cases; "
                f"SHA-256 {assembly_artifacts.dataset_sha256}."
            )
            print(f"Canonical dataset: {assembly_artifacts.canonical_path}")
            return 0
        if args.command == "export":
            export_artifacts = export_dataset(
                args.root,
                public_path=args.public_output,
                private_path=args.private_output,
            )
            print(f"Exported {export_artifacts.case_count} public/private joined cases.")
            print(
                f"Public input: {export_artifacts.public_path} "
                f"(SHA-256 {export_artifacts.public_sha256})"
            )
            print(
                f"Private answers: {export_artifacts.private_path} "
                f"(SHA-256 {export_artifacts.private_sha256})"
            )
            return 0
        if args.command == "jev-review":
            return _run_jev(args)
    except (DatasetFailure, OSError, ValueError) as error:
        print(f"query-gold failed: {error}", file=sys.stderr)
        return 1
    parser.error("unknown command")
    return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
