"""Constrained-quality ranking of every provider, per category and overall.

Per (category c, provider p) over evaluated queries (missing excluded, failures scored 0):
  Q_hat(c,p) = (sum Q + alpha * Qbar(p)) / (n + alpha)        shrunk toward provider mean
  Q_LCB, Q_UCB = paired-bootstrap quantiles of Q_hat            (same resampled queries for all)
  rho(c,p)  = (1 + successes) / (2 + evaluated)                 Beta(1,1) posterior reliability
  U(c,p)    = V*Q_hat - C_mean - kappa*L90/1000 - phi*(1 - rho)  dollar tie-breaker

Ordering (a full ranking, not just a winner):
  1. Status groups: ranked, then constraint violations (L90 > L_max, C > C_max, success
     rate < minimum), then insufficient coverage.
  2. Within a group, providers are sorted by Q_LCB. A provider joins the current tier unless
     the tier leader beats it in at least `tie_confidence` of paired bootstrap draws.
  3. Within a tier (statistically tied on quality), providers are ordered by utility U.
Failures lower Q_hat directly (Q = 0), lower rho (phi penalty in U), and can violate the
success-rate constraint; zero-result responses count as failures.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

from search_scoring.loading import QueryOutcome

Status = Literal["ranked", "constraint_violation", "insufficient_coverage"]
FloatArray = npt.NDArray[np.float64]
_GROUP_ORDER: tuple[Status, ...] = ("ranked", "constraint_violation", "insufficient_coverage")


@dataclass(frozen=True, slots=True)
class RankingParams:
    shrinkage: float = 10.0
    bootstrap: int = 2000
    lcb_quantile: float = 0.10
    tie_confidence: float = 0.90
    value_usd: float = 0.20
    latency_usd_per_second: float = 0.001
    failure_usd: float = 0.02
    max_latency_p90_ms: float | None = 10_000.0
    max_cost_usd: float | None = 0.02
    min_success_rate: float = 0.0
    min_coverage: float = 0.8
    seed: int = 0


@dataclass(frozen=True, slots=True)
class ProviderStats:
    evaluated: int
    total: int
    successes: int
    failures: int
    missing: int
    failure_reasons: dict[str, int]
    quality_raw: float | None
    answer_hit_rate: float | None
    answer_scored: int
    url_hit_rate: float | None
    domain_hit_rate: float | None
    success_rate: float | None
    reliability: float
    latency_p50_ms: float | None
    latency_p90_ms: float | None
    cost_mean_usd: float | None
    cost_unknown: int


@dataclass(frozen=True, slots=True)
class Standing:
    scope: str
    rank: int
    tier: int
    provider: str
    status: Status
    violations: tuple[str, ...]
    quality: float
    quality_lcb: float
    quality_ucb: float
    p_below_tier_leader: float | None
    utility_usd: float
    stats: ProviderStats


def _mean(values: Sequence[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _percentile(values: Sequence[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def provider_stats(outcomes: Sequence[QueryOutcome]) -> ProviderStats:
    evaluated = [o for o in outcomes if o.outcome != "missing"]
    successes = sum(o.outcome == "success" for o in evaluated)
    scored = [o for o in evaluated if o.answer_informative]
    answer_hits = [
        o.relevance.answer_hit if o.relevance and o.relevance.answer_hit is not None else 0.0
        for o in scored
    ]
    latencies = [o.latency_ms for o in evaluated if o.latency_ms is not None]
    costs = [o.cost_usd for o in evaluated if o.cost_usd is not None]
    return ProviderStats(
        evaluated=len(evaluated),
        total=len(outcomes),
        successes=successes,
        failures=len(evaluated) - successes,
        missing=len(outcomes) - len(evaluated),
        failure_reasons=dict(
            Counter(o.reason or "unknown" for o in evaluated if o.outcome == "failure")
        ),
        quality_raw=_mean([o.quality for o in evaluated if o.quality is not None]),
        answer_hit_rate=_mean(answer_hits),
        answer_scored=len(scored),
        url_hit_rate=_mean([o.relevance.url_hit if o.relevance else 0.0 for o in evaluated]),
        domain_hit_rate=_mean([o.relevance.domain_hit if o.relevance else 0.0 for o in evaluated]),
        success_rate=successes / len(evaluated) if evaluated else None,
        reliability=(1 + successes) / (2 + len(evaluated)),
        latency_p50_ms=_percentile(latencies, 50),
        latency_p90_ms=_percentile(latencies, 90),
        cost_mean_usd=_mean(costs),
        cost_unknown=len(evaluated) - len(costs),
    )


def quality_matrix(
    outcomes: Mapping[str, Sequence[QueryOutcome]], providers: Sequence[str]
) -> FloatArray:
    """Providers x queries quality, NaN where the outcome is missing."""
    return np.array(
        [
            [np.nan if o.quality is None else o.quality for o in outcomes[provider]]
            for provider in providers
        ],
        dtype=np.float64,
    )


def bootstrap_quality(
    quality: FloatArray, prior: FloatArray, params: RankingParams, rng: np.random.Generator
) -> tuple[FloatArray, FloatArray]:
    """Point estimate (P,) and paired bootstrap draws (B, P) of shrunk mean quality."""

    def shrunk(values: FloatArray) -> FloatArray:
        present = ~np.isnan(values)
        total = np.where(present, values, 0.0).sum(axis=-1)
        count = present.sum(axis=-1)
        prior_b = np.broadcast_to(prior.reshape((-1,) + (1,) * (total.ndim - 1)), total.shape)
        return np.asarray(
            (total + params.shrinkage * prior_b) / (count + params.shrinkage), dtype=np.float64
        )

    n = quality.shape[1]
    draws = rng.integers(0, n, size=(params.bootstrap, n))
    samples = shrunk(quality[:, draws])  # (P, B)
    return shrunk(quality), np.asarray(samples.T, dtype=np.float64)


def _status(stats: ProviderStats, params: RankingParams) -> tuple[Status, tuple[str, ...]]:
    if stats.total == 0 or stats.evaluated / stats.total < params.min_coverage:
        return "insufficient_coverage", (f"coverage {stats.evaluated}/{stats.total}",)
    violations: list[str] = []
    if (
        params.max_latency_p90_ms is not None
        and stats.latency_p90_ms is not None
        and stats.latency_p90_ms > params.max_latency_p90_ms
    ):
        violations.append(
            f"latency_p90 {stats.latency_p90_ms:.0f}ms > {params.max_latency_p90_ms:.0f}ms"
        )
    if (
        params.max_cost_usd is not None
        and stats.cost_mean_usd is not None
        and stats.cost_mean_usd > params.max_cost_usd
    ):
        violations.append(f"cost ${stats.cost_mean_usd:.4f} > ${params.max_cost_usd:.4f}")
    if stats.success_rate is not None and stats.success_rate < params.min_success_rate:
        violations.append(f"success_rate {stats.success_rate:.2f} < {params.min_success_rate:.2f}")
    return ("constraint_violation" if violations else "ranked"), tuple(violations)


def utility(quality: float, stats: ProviderStats, params: RankingParams) -> float:
    return (
        params.value_usd * quality
        - (stats.cost_mean_usd or 0.0)
        - params.latency_usd_per_second * (stats.latency_p90_ms or 0.0) / 1000.0
        - params.failure_usd * (1.0 - stats.reliability)
    )


def rank_scope(
    scope: str,
    providers: Sequence[str],
    point: FloatArray,
    samples: FloatArray,
    stats: Mapping[str, ProviderStats],
    params: RankingParams,
) -> list[Standing]:
    """Fully order providers into statistically separated tiers for one scope."""
    lcb = np.quantile(samples, params.lcb_quantile, axis=0)
    ucb = np.quantile(samples, 1.0 - params.lcb_quantile, axis=0)
    statuses = {p: _status(stats[p], params) for p in providers}
    utilities = {p: utility(float(point[i]), stats[p], params) for i, p in enumerate(providers)}
    index = {p: i for i, p in enumerate(providers)}
    standings: list[Standing] = []
    tier = 0
    for group in _GROUP_ORDER:
        members = sorted(
            (p for p in providers if statuses[p][0] == group),
            key=lambda p: (-lcb[index[p]], -point[index[p]], p),
        )
        tiers: list[list[tuple[str, float | None]]] = []
        for provider in members:
            if tiers:
                leader = tiers[-1][0][0]
                a, b = samples[:, index[leader]], samples[:, index[provider]]
                beaten = float(np.mean(a > b) + 0.5 * np.mean(a == b))
                if beaten < params.tie_confidence:
                    tiers[-1].append((provider, beaten))
                    continue
                tiers.append([(provider, beaten)])
            else:
                tiers.append([(provider, None)])
        for members_in_tier in tiers:
            tier += 1
            leader_name = members_in_tier[0][0]
            ordered = sorted(members_in_tier, key=lambda item: (-utilities[item[0]], item[0]))
            for provider, p_below in ordered:
                i = index[provider]
                standings.append(
                    Standing(
                        scope=scope,
                        rank=len(standings) + 1,
                        tier=tier,
                        provider=provider,
                        status=group,
                        violations=statuses[provider][1],
                        quality=float(point[i]),
                        quality_lcb=float(lcb[i]),
                        quality_ucb=float(ucb[i]),
                        p_below_tier_leader=None if provider == leader_name else p_below,
                        utility_usd=utilities[provider],
                        stats=stats[provider],
                    )
                )
    return standings


def rank_all(
    outcomes: Mapping[str, Sequence[QueryOutcome]], params: RankingParams
) -> tuple[dict[str, list[Standing]], list[Standing]]:
    """Rank every provider in each category, and overall by macro-averaged category quality."""
    providers = sorted(outcomes)
    if not providers:
        raise ValueError("at least one provider is required")
    case_order = [o.case_id for o in outcomes[providers[0]]]
    if any([o.case_id for o in outcomes[p]] != case_order for p in providers):
        raise ValueError("every provider must be scored on the same ordered cases")
    rng = np.random.default_rng(params.seed)
    all_quality = quality_matrix(outcomes, providers)
    present = ~np.isnan(all_quality)
    prior = np.divide(
        np.where(present, all_quality, 0.0).sum(axis=1),
        present.sum(axis=1),
        out=np.zeros(len(providers)),
        where=present.sum(axis=1) > 0,
    )
    categories = sorted({o.category for o in outcomes[providers[0]]})
    by_category: dict[str, list[Standing]] = {}
    points: list[FloatArray] = []
    draws: list[FloatArray] = []
    for category in categories:
        columns = [i for i, o in enumerate(outcomes[providers[0]]) if o.category == category]
        subset = {p: [outcomes[p][i] for i in columns] for p in providers}
        point, samples = bootstrap_quality(all_quality[:, columns], prior, params, rng)
        stats = {p: provider_stats(subset[p]) for p in providers}
        by_category[category] = rank_scope(category, providers, point, samples, stats, params)
        points.append(point)
        draws.append(samples)
    overall_point = np.asarray(np.mean(points, axis=0), dtype=np.float64)
    overall_samples = np.asarray(np.mean(draws, axis=0), dtype=np.float64)
    overall_stats = {p: provider_stats(outcomes[p]) for p in providers}
    overall = rank_scope(
        "overall", providers, overall_point, overall_samples, overall_stats, params
    )
    return by_category, overall
