"""Offline CLI: score collected search runs against private answers and rank providers."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from query_gold.io import atomic_write_many, json_bytes, jsonl_bytes, sha256_file
from search_scoring.loading import (
    QueryOutcome,
    RunSource,
    discover_run,
    explicit_run,
    load_answers,
    load_outcomes,
    load_questions,
)
from search_scoring.ranking import RankingParams, Standing, rank_all
from search_scoring.relevance import RelevanceWeights
from search_urls.runner import repository_root

DEFAULT_PROVIDERS = ("brave", "exa", "keenable", "parallel", "tavily", "tinyfish", "you")
METHOD = "constrained-quality/v1"


def build_parser() -> argparse.ArgumentParser:
    defaults, weights = RankingParams(), RelevanceWeights()
    parser = argparse.ArgumentParser(
        prog="score-search",
        description="Score direct search collections offline and rank providers per category.",
    )
    parser.add_argument("--benchmark", type=Path, required=True, help="Public question JSONL.")
    parser.add_argument("--answers", type=Path, required=True, help="Private answer JSONL.")
    parser.add_argument(
        "--results-root", type=Path, default=Path("benchmarks/eval_v2/search_results")
    )
    parser.add_argument("--providers", default=",".join(DEFAULT_PROVIDERS))
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        metavar="PROVIDER=DIR",
        help="Use this collection directory for a provider instead of auto-discovery.",
    )
    parser.add_argument("--output", type=Path, default=Path("results/search-scoring"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--answer-weight", type=float, default=weights.answer)
    parser.add_argument("--url-weight", type=float, default=weights.url)
    parser.add_argument("--domain-weight", type=float, default=weights.domain)
    parser.add_argument("--shrinkage", type=float, default=defaults.shrinkage)
    parser.add_argument("--bootstrap", type=int, default=defaults.bootstrap)
    parser.add_argument("--lcb-quantile", type=float, default=defaults.lcb_quantile)
    parser.add_argument("--tie-confidence", type=float, default=defaults.tie_confidence)
    parser.add_argument("--value-usd", type=float, default=defaults.value_usd)
    parser.add_argument(
        "--latency-usd-per-second", type=float, default=defaults.latency_usd_per_second
    )
    parser.add_argument("--failure-usd", type=float, default=defaults.failure_usd)
    parser.add_argument("--max-latency-p90-ms", type=float, default=defaults.max_latency_p90_ms)
    parser.add_argument("--max-cost-usd", type=float, default=defaults.max_cost_usd)
    parser.add_argument("--no-latency-limit", action="store_true")
    parser.add_argument("--no-cost-limit", action="store_true")
    parser.add_argument("--min-success-rate", type=float, default=defaults.min_success_rate)
    parser.add_argument("--min-coverage", type=float, default=defaults.min_coverage)
    parser.add_argument("--seed", type=int, default=defaults.seed)
    return parser


def _params(args: argparse.Namespace) -> RankingParams:
    if args.bootstrap < 100 or not 0 < args.lcb_quantile < 0.5:
        raise ValueError("bootstrap must be >= 100 and lcb-quantile in (0, 0.5)")
    if not 0.5 < args.tie_confidence < 1 or args.shrinkage < 0:
        raise ValueError("tie-confidence must be in (0.5, 1) and shrinkage non-negative")
    return RankingParams(
        shrinkage=args.shrinkage,
        bootstrap=args.bootstrap,
        lcb_quantile=args.lcb_quantile,
        tie_confidence=args.tie_confidence,
        value_usd=args.value_usd,
        latency_usd_per_second=args.latency_usd_per_second,
        failure_usd=args.failure_usd,
        max_latency_p90_ms=None if args.no_latency_limit else args.max_latency_p90_ms,
        max_cost_usd=None if args.no_cost_limit else args.max_cost_usd,
        min_success_rate=args.min_success_rate,
        min_coverage=args.min_coverage,
        seed=args.seed,
    )


def _weights(args: argparse.Namespace) -> RelevanceWeights:
    weights = RelevanceWeights(args.answer_weight, args.url_weight, args.domain_weight)
    total = weights.answer + weights.url + weights.domain
    if (
        min(asdict(weights).values()) < 0
        or abs(total - 1.0) > 1e-9
        or weights.url + weights.domain <= 0
    ):
        raise ValueError("relevance weights must be non-negative and sum to 1")
    return weights


def _sources(args: argparse.Namespace, root: Path, dataset_sha256: str) -> list[RunSource]:
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    overrides: dict[str, Path] = {}
    for item in args.run:
        provider, separator, directory = item.partition("=")
        if not separator or provider not in providers:
            raise ValueError(f"--run must be PROVIDER=DIR for a selected provider: {item}")
        overrides[provider] = Path(directory) if Path(directory).is_absolute() else root / directory
    results_root = (
        args.results_root if args.results_root.is_absolute() else root / args.results_root
    )
    return [
        explicit_run(p, overrides[p], dataset_sha256)
        if p in overrides
        else discover_run(results_root, p, dataset_sha256)
        for p in providers
    ]


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _standing_row(standing: Standing) -> dict[str, Any]:
    stats = standing.stats
    return {
        "scope": standing.scope,
        "rank": standing.rank,
        "tier": standing.tier,
        "provider": standing.provider,
        "status": standing.status,
        "violations": list(standing.violations),
        "quality": _round(standing.quality),
        "qualityLcb": _round(standing.quality_lcb),
        "qualityUcb": _round(standing.quality_ucb),
        "qualityRaw": _round(stats.quality_raw),
        "pBelowTierLeader": _round(standing.p_below_tier_leader, 3),
        "utilityUsd": _round(standing.utility_usd, 5),
        "answerHitRate": _round(stats.answer_hit_rate),
        "answerScoredQueries": stats.answer_scored,
        "urlHitRate": _round(stats.url_hit_rate),
        "domainHitRate": _round(stats.domain_hit_rate),
        "successRate": _round(stats.success_rate),
        "reliability": _round(stats.reliability),
        "evaluated": stats.evaluated,
        "successes": stats.successes,
        "failures": stats.failures,
        "missing": stats.missing,
        "failureReasons": stats.failure_reasons,
        "latencyP50Ms": _round(stats.latency_p50_ms, 1),
        "latencyP90Ms": _round(stats.latency_p90_ms, 1),
        "costMeanUsd": _round(stats.cost_mean_usd, 6),
        "costUnknown": stats.cost_unknown,
    }


def _query_row(outcome: QueryOutcome) -> dict[str, Any]:
    relevance = outcome.relevance
    return {
        "provider": outcome.provider,
        "caseId": outcome.case_id,
        "category": outcome.category,
        "outcome": outcome.outcome,
        "reason": outcome.reason,
        "quality": _round(outcome.quality),
        "answerInformative": outcome.answer_informative,
        "answerHit": _round(relevance.answer_hit) if relevance else None,
        "answerRank": relevance.answer_rank if relevance else None,
        "urlHit": _round(relevance.url_hit) if relevance else None,
        "urlRank": relevance.url_rank if relevance else None,
        "domainHit": _round(relevance.domain_hit) if relevance else None,
        "resultCount": outcome.result_count,
        "attempts": outcome.attempts,
        "latencyMs": _round(outcome.latency_ms, 1),
        "costUsd": _round(outcome.cost_usd, 6),
    }


def _csv(rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()}
        )
    return buffer.getvalue().encode("utf-8")


def _rank_matrix(by_category: dict[str, list[Standing]], providers: int) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["category", *[f"rank_{i}" for i in range(1, providers + 1)]])
    for category, standings in by_category.items():
        cells = []
        for s in standings:
            flag = "" if s.status == "ranked" else f", {s.status}"
            cells.append(f"{s.provider} (T{s.tier}, Q={s.quality:.3f}{flag})")
        writer.writerow([category, *cells])
    return buffer.getvalue().encode("utf-8")


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = repository_root()
    benchmark = args.benchmark if args.benchmark.is_absolute() else root / args.benchmark
    answers_path = args.answers if args.answers.is_absolute() else root / args.answers
    params, weights = _params(args), _weights(args)
    questions = load_questions(benchmark)
    answers = load_answers(answers_path, questions)
    sources = _sources(args, root, questions.sha256)
    outcomes = {
        s.provider: load_outcomes(s, questions, answers, k=args.top_k, weights=weights)
        for s in sources
    }
    by_category, overall = rank_all(outcomes, params)

    generated_at = datetime.now(UTC)
    output_root = args.output if args.output.is_absolute() else root / args.output
    directory = output_root / generated_at.strftime("%Y-%m-%dT%H-%M-%SZ")
    category_rows = [_standing_row(s) for standings in by_category.values() for s in standings]
    overall_rows = [_standing_row(s) for s in overall]
    columns = list(category_rows[0])
    manifest = {
        "schemaVersion": "search-scoring/v1",
        "method": METHOD,
        "generatedAt": generated_at.isoformat(),
        "benchmark": {"path": str(args.benchmark), "sha256": questions.sha256},
        "answers": {"path": str(args.answers), "sha256": sha256_file(answers_path)},
        "runs": [
            {
                "provider": s.provider,
                "directory": str(
                    s.directory.relative_to(root)
                    if s.directory.is_relative_to(root)
                    else s.directory
                ),
                "configSHA256": s.config_sha256,
                "datasetSHA256": s.dataset_sha256,
            }
            for s in sources
        ],
        "topK": args.top_k,
        "relevanceWeights": asdict(weights),
        "rankingParams": asdict(params),
        "outcomeRules": {
            "success": "results returned; quality = rank-discounted relevance R",
            "failure": "provider error or zero results; quality = 0",
            "missing": "billing 402, harness request_limit, cancelled, or no record; excluded",
        },
    }
    atomic_write_many(
        {
            directory / "per_query.jsonl": jsonl_bytes(
                [_query_row(o) for provider in sorted(outcomes) for o in outcomes[provider]]
            ),
            directory / "category_rankings.jsonl": jsonl_bytes(category_rows),
            directory / "category_rankings.csv": _csv(category_rows, columns),
            directory / "overall_ranking.json": json_bytes(overall_rows, pretty=True),
            directory / "overall_ranking.csv": _csv(overall_rows, columns),
            directory / "rank_matrix.csv": _rank_matrix(by_category, len(sources)),
            directory / "manifest.json": json_bytes(manifest, pretty=True),
        }
    )
    summary = {
        "output": str(directory.relative_to(root) if directory.is_relative_to(root) else directory),
        "overall": [
            {
                "rank": s.rank,
                "tier": s.tier,
                "provider": s.provider,
                "quality": round(s.quality, 4),
                "status": s.status,
            }
            for s in overall
        ],
    }
    print(json.dumps(summary, separators=(",", ":")))
    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except ValueError as error:
        print(f"score-search failed: {str(error)[:300]}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
