"""Edge cases for the T-threshold and top-N screening selection."""

import pytest

from hannovators_deep_researcher.models.enums import RejectionCode
from hannovators_deep_researcher.services.pipeline.stages.screen.selection import (
    ScreenResult,
    select,
)


def _result(source_id: str, votes: int | None, relevance: float = 2.0) -> ScreenResult:
    return ScreenResult(source_id=source_id, relevance=relevance, confidence=0.8, votes=votes)


@pytest.mark.unit
def test_votes_exactly_at_threshold_are_eligible() -> None:
    results = [_result("at", votes=2, relevance=1.0), _result("below", votes=1, relevance=4.0)]

    decisions = select(results, votes_t=2, top_n=5)

    at, below = decisions
    assert at.promoted
    assert at.rejection_code is None
    assert not below.promoted
    assert below.rejection_code is RejectionCode.VOTES_BELOW_T


@pytest.mark.unit
def test_fewer_candidates_than_top_n_promotes_every_eligible_one() -> None:
    results = [_result("a", 3, 3.0), _result("b", 2, 1.0), _result("c", None, 0.5)]

    decisions = select(results, votes_t=2, top_n=15)

    assert all(decision.promoted for decision in decisions)
    assert all(decision.rejection_code is None for decision in decisions)
