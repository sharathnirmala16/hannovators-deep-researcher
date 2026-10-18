"""Pure ranking helpers shared by retrieval and screening."""

from collections.abc import Hashable, Sequence
from statistics import fmean, pstdev

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion[T: Hashable](
    rankings: Sequence[Sequence[T]], *, k: int = DEFAULT_RRF_K
) -> list[tuple[T, float]]:
    """Fuse ranked lists with RRF: `score(item) = sum(1 / (k + rank))`, rank starting at 1.

    Returns `(item, score)` pairs, best first. Equal scores keep the order in which items first
    appear across the lists, so the output is deterministic. An item repeated inside one list
    counts only at its best rank.
    """

    if k < 0:
        raise ValueError("k must not be negative")
    scores: dict[T, float] = {}
    for ranking in rankings:
        seen: set[T] = set()
        for rank, item in enumerate(ranking, start=1):
            if item in seen:
                continue
            seen.add(item)
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


def z_scores(values: Sequence[float]) -> list[float]:
    """Standard scores with the population standard deviation.

    Zero variance (including a single value) gives 0.0 for every value; no input gives `[]`.
    """

    if not values:
        return []
    mean = fmean(values)
    deviation = pstdev(values, mu=mean)
    if deviation == 0.0:
        return [0.0 for _ in values]
    return [(value - mean) / deviation for value in values]
