"""Edge cases for the pure ranking helpers."""

import pytest

from hannovators_deep_researcher.services.ranking import reciprocal_rank_fusion, z_scores


@pytest.mark.unit
def test_z_scores_with_zero_variance_are_all_zero() -> None:
    assert z_scores([3.0, 3.0, 3.0]) == [0.0, 0.0, 0.0]


@pytest.mark.unit
def test_z_scores_with_one_item_is_zero() -> None:
    assert z_scores([7.5]) == [0.0]


@pytest.mark.unit
def test_rrf_with_empty_lists() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
    assert reciprocal_rank_fusion([[], ["a"]]) == [("a", 1 / 61)]


@pytest.mark.unit
def test_rrf_ties_keep_first_appearance_order() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a"]])

    assert [item for item, _ in fused] == ["a", "b", "c"]
    assert fused[0][1] == pytest.approx(fused[1][1])
