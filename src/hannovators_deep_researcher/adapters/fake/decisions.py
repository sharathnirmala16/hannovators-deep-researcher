"""Fake Jev System One: stable, varied, valid answers from a hash of (state, question key)."""

import hashlib
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from hannovators_deep_researcher.models.decisions import DecisionAnswer, DecisionQuestion
from hannovators_deep_researcher.models.enums import DecisionQuestionType

if TYPE_CHECKING:
    from hannovators_deep_researcher.models.ports import DecisionModel

_PRECISION = 6
# Raising uniform hash values to this power peaks the distributions, so confidence varies.
_PEAKING = 3
_WEIGHT_FLOOR = 0.01
_HASH_MAX = float(2**64 - 1)


class FakeDecisionModel:
    """Answers any question without a network call. The same input gives the same answer."""

    async def evaluate(
        self, state: str, questions: Mapping[str, DecisionQuestion]
    ) -> dict[str, DecisionAnswer]:
        return {key: answer(state, key, question) for key, question in questions.items()}


def answer(state: str, key: str, question: DecisionQuestion) -> DecisionAnswer:
    criteria = question.criteria
    match question.type:
        case DecisionQuestionType.CHOICE:
            return _choice(state, key, list(criteria or ()))
        case DecisionQuestionType.SCORE:
            return _score(state, key, list(criteria or ()))
        case DecisionQuestionType.NOUL:
            return _noul(state, key)


def _choice(state: str, key: str, options: Sequence[str]) -> DecisionAnswer:
    probabilities = _distribution(state, key, options)
    chosen = max(options, key=probabilities.__getitem__)
    return DecisionAnswer(
        type=DecisionQuestionType.CHOICE,
        choice=chosen,
        confidence=probabilities[chosen],
        probabilities=probabilities,
    )


def _score(state: str, key: str, levels: Sequence[str]) -> DecisionAnswer:
    probabilities = _distribution(state, key, levels)
    expected = sum(index * probabilities[level] for index, level in enumerate(levels))
    return DecisionAnswer(
        type=DecisionQuestionType.SCORE,
        score=round(expected, _PRECISION),
        confidence=max(probabilities.values()),
        probabilities=probabilities,
    )


def _noul(state: str, key: str) -> DecisionAnswer:
    value = round(_unit(state, key), _PRECISION)
    return DecisionAnswer(
        type=DecisionQuestionType.NOUL,
        noul=value,
        probabilities={"true": value, "false": round(1.0 - value, _PRECISION)},
    )


def _distribution(state: str, key: str, options: Sequence[str]) -> dict[str, float]:
    weights = {option: _unit(state, key, option) ** _PEAKING + _WEIGHT_FLOOR for option in options}
    total = sum(weights.values())
    return {option: round(weight / total, _PRECISION) for option, weight in weights.items()}


def _unit(*parts: str) -> float:
    """A stable value in [0, 1] for the given parts."""

    digest = hashlib.blake2b("\x1f".join(parts).encode(), digest_size=8).digest()
    return int.from_bytes(digest) / _HASH_MAX


if TYPE_CHECKING:
    _decision_model: DecisionModel = FakeDecisionModel()
