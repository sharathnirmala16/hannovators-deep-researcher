"""Command-line interface for direct provider search collection."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from search_urls.runner import repository_root, run_collection
from search_urls.transport import SearchProviderError


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _repo_path(value: Path, root: Path) -> Path:
    return value if value.is_absolute() else root / value


def build_parser() -> argparse.ArgumentParser:
    root = repository_root()
    parser = argparse.ArgumentParser(
        prog="search-urls",
        description="Collect direct search results from one configured provider.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("benchmarks/configs/search_configs/exa.json"),
        help="Provider settings JSON (default: benchmarks/configs/search_configs/exa.json).",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        required=True,
        help="Explicit public answer-free query JSONL input.",
    )
    parser.add_argument(
        "--max-queries",
        type=_positive_int,
        default=None,
        metavar="N",
        help="Limit this invocation to at most N pending input cases.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Rerun queries whose latest saved result is a terminal provider error.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=root / ".env",
        help="Credential environment file loaded at runtime (default: repository .env).",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable stderr progress updates.",
    )
    return parser


def _emit_failure(error: Exception, *, safe_detail: str | None = None) -> NoReturn:
    # Keep provider response bodies and credentials out of terminal output.
    detail = safe_detail if safe_detail is not None else type(error).__name__
    print(f"search-urls failed: {detail}", file=sys.stderr)
    raise SystemExit(1)


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = repository_root()
    try:
        summary = asyncio.run(
            run_collection(
                config_path=_repo_path(args.config, root),
                benchmark_path=_repo_path(args.benchmark, root),
                env_file=_repo_path(args.env_file, root),
                max_queries=args.max_queries,
                retry_failed=args.retry_failed,
                progress=not args.no_progress,
            )
        )
    except KeyboardInterrupt:
        return 130
    except SearchProviderError as error:
        _emit_failure(
            error,
            safe_detail=f"provider={error.provider} code={error.code}",
        )
    except ValueError as error:
        # Config and run-store messages are deliberately sanitized at their source.
        _emit_failure(error, safe_detail=str(error).replace("\n", " ")[:240])
    except Exception as error:
        _emit_failure(error)
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
    return 130 if summary.get("status") == "interrupted" else 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
