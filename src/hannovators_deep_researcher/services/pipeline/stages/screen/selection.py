"""Pure screening selection: T-threshold eligibility, z-score ranking, top-N promotion."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from hannovators_deep_researcher.models.enums import RejectionCode
from hannovators_deep_researcher.services.ranking import z_scores

VOTE_THRESHOLD = 0.5


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

    @property
    def strength(self) -> float:
        return self.relevance * self.confidence


@dataclass(frozen=True, slots=True)
class ScreenDecision:
    result: ScreenResult
    z: float
    promoted: bool
    rejection_code: RejectionCode | None
    explanation: str


def count_votes(values: Sequence[float | None]) -> int:
    return sum(value is not None and value >= VOTE_THRESHOLD for value in values)


def is_eligible(result: ScreenResult, votes_t: int) -> bool:
    return result.votes is None or result.votes >= votes_t


def select(results: Sequence[ScreenResult], *, votes_t: int, top_n: int) -> list[ScreenDecision]:
    """Promote the top `top_n` eligible results by z(relevance x confidence); explain the rest."""

    zs = z_scores([result.strength for result in results])
    ranked = sorted(range(len(results)), key=lambda index: zs[index], reverse=True)
    eligible = [index for index in ranked if is_eligible(results[index], votes_t)]
    promoted = set(eligible[:top_n])
    return [
        _decide(result, zs[index], index in promoted, votes_t, top_n)
        for index, result in enumerate(results)
    ]


def _decide(
    result: ScreenResult, z: float, promoted: bool, votes_t: int, top_n: int
) -> ScreenDecision:
    votes = "embedding fallback" if result.votes is None else f"{result.votes} votes (T={votes_t})"
    if promoted:
        return ScreenDecision(
            result,
            z,
            True,
            None,
            f"Promoted: {votes}, relevance {result.relevance:.2f}, z {z:+.2f}.",
        )
    if is_eligible(result, votes_t):
        return ScreenDecision(
            result,
            z,
            False,
            RejectionCode.LOW_RELEVANCE,
            f"Eligible with {votes}, but z {z:+.2f} ranks below the top {top_n}.",
        )
    exclusion = result.exclusion or ""
    if exclusion in RejectionCode.__members__:
        return ScreenDecision(
            result,
            z,
            False,
            RejectionCode(exclusion),
            f"Only {votes}; exclusion reason: {exclusion}.",
        )
    return ScreenDecision(result, z, False, RejectionCode.VOTES_BELOW_T, f"Only {votes}.")
