"""Pure screening selection: T-threshold eligibility, evidence-hierarchy ranking, top-N promotion.

Eligible candidates (votes >= T) that are at least moderately relevant rank by evidence level
first (meta-analysis before RCT before cohort ...), then by z(relevance x confidence); weakly
relevant ones follow in the same order. About a quarter of the N slots are reserved for the
best relevant opposing, null, mixed, or alternative evidence (opposing and null first), so
supportive records cannot crowd disconfirming evidence out of the review.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from hannovators_deep_researcher.models.enums import EvidenceLevel, EvidenceStance, RejectionCode
from hannovators_deep_researcher.services.evidence import evidence_rank, is_contrarian, is_opposing
from hannovators_deep_researcher.services.ranking import z_scores

VOTE_THRESHOLD = 0.5
MIN_RELEVANCE = 2.0
"""Jev relevance 0..4; 2 = "Moderately relevant". Weaker records rank after relevant ones."""
RESERVE_SHARE = 0.25
MIN_N_FOR_RESERVE = 2


@dataclass(frozen=True, slots=True)
class ScreenResult:
    """One screened candidate. `votes is None` marks the embedding fallback (no votes)."""

    source_id: str
    relevance: float
    confidence: float
    votes: int | None
    exclusion: str | None = None
    method: str = "jev"
    details: Mapping[str, object] = field(default_factory=dict)
    evidence_level: EvidenceLevel | None = None
    stance: EvidenceStance | None = None

    @property
    def strength(self) -> float:
        return self.relevance * self.confidence

    @property
    def evidence_rank(self) -> int:
        return evidence_rank(self.evidence_level)

    @property
    def is_relevant(self) -> bool:
        """At least moderately relevant; the embedding fallback has no such scale."""

        return self.votes is None or self.relevance >= MIN_RELEVANCE


@dataclass(frozen=True, slots=True)
class ScreenDecision:
    result: ScreenResult
    z: float
    promoted: bool
    rejection_code: RejectionCode | None
    explanation: str
    reserved: bool = False
    position: int | None = None
    """1-based rank among promoted candidates; None when not promoted."""


def count_votes(values: Sequence[float | None]) -> int:
    return sum(value is not None and value >= VOTE_THRESHOLD for value in values)


def is_eligible(result: ScreenResult, votes_t: int) -> bool:
    return result.votes is None or result.votes >= votes_t


def reserved_slots(top_n: int, share: float = RESERVE_SHARE) -> int:
    return max(1, round(top_n * share)) if top_n >= MIN_N_FOR_RESERVE else 0


def select(
    results: Sequence[ScreenResult],
    *,
    votes_t: int,
    top_n: int,
    reserve_share: float = RESERVE_SHARE,
) -> list[ScreenDecision]:
    """Promote `top_n` eligible results ranked by (evidence rank, -z); explain the rest."""

    zs = z_scores([result.strength for result in results])

    def order(index: int) -> tuple[int, int, float]:
        return (
            0 if results[index].is_relevant else 1,
            results[index].evidence_rank,
            -zs[index],
        )

    eligible = sorted(
        (index for index, result in enumerate(results) if is_eligible(result, votes_t)), key=order
    )
    contrarian = sorted(
        (
            index
            for index in eligible
            if is_contrarian(results[index].stance) and results[index].is_relevant
        ),
        key=lambda index: (0 if is_opposing(results[index].stance) else 1, *order(index)),
    )
    reserved = contrarian[: min(reserved_slots(top_n, reserve_share), top_n)]
    rest = [index for index in eligible if index not in reserved][: top_n - len(reserved)]
    chosen = set(reserved) | set(rest)
    positions = {index: rank for rank, index in enumerate(sorted(chosen, key=order), start=1)}
    # Reserved slots that changed the outcome: the plain ranking would have cut them.
    reserved_set = set(reserved) - set(eligible[:top_n])
    return [
        _decide(
            result,
            zs[index],
            votes_t,
            top_n,
            position=positions.get(index),
            reserved=index in reserved_set,
        )
        for index, result in enumerate(results)
    ]


def _level(result: ScreenResult) -> str:
    level = result.evidence_level or "unknown design"
    stance = f", {result.stance}" if result.stance else ""
    return f"{level}{stance}"


def _decide(
    result: ScreenResult,
    z: float,
    votes_t: int,
    top_n: int,
    *,
    position: int | None,
    reserved: bool,
) -> ScreenDecision:
    votes = "embedding fallback" if result.votes is None else f"{result.votes} votes (T={votes_t})"
    facts = f"{votes}, {_level(result)}, relevance {result.relevance:.2f}, z {z:+.2f}"
    if position is not None:
        why = " Kept in a slot reserved for opposing or alternative evidence." if reserved else ""
        return ScreenDecision(
            result,
            z,
            True,
            None,
            f"Promoted #{position}: {facts}.{why}",
            reserved=reserved,
            position=position,
        )
    if is_eligible(result, votes_t):
        return ScreenDecision(
            result,
            z,
            False,
            RejectionCode.LOW_RELEVANCE,
            f"Eligible with {facts}, but ranks below the top {top_n} "
            "(relevant records first, then evidence level, then z).",
        )
    exclusion = result.exclusion or ""
    if exclusion in RejectionCode.__members__:
        return ScreenDecision(
            result,
            z,
            False,
            RejectionCode(exclusion),
            f"Only {facts}; exclusion reason: {exclusion}.",
        )
    return ScreenDecision(result, z, False, RejectionCode.VOTES_BELOW_T, f"Only {facts}.")
