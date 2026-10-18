"""Jev System One question and answer models."""

from typing import Self

from pydantic import Field, model_validator

from hannovators_deep_researcher.models.base import ContractModel, Probability
from hannovators_deep_researcher.models.enums import DecisionQuestionType

MAX_CHOICE_OPTIONS = 20
NOUL_CRITERIA_KEYS = frozenset({"true", "false"})


class DecisionQuestion(ContractModel):
    """One named question in a Jev request.

    `criteria` depends on `type`: a map of option -> description (or None) for `choice`
    (at most 20 options), an ordered list of levels for `score`, and optionally
    `{"true": ..., "false": ...}` for `noul`.
    """

    type: DecisionQuestionType
    instructions: str
    criteria: dict[str, str | None] | list[str] | None = None

    @model_validator(mode="after")
    def _check_criteria(self) -> Self:
        criteria = self.criteria
        match self.type:
            case DecisionQuestionType.CHOICE:
                if not isinstance(criteria, dict) or not 1 <= len(criteria) <= MAX_CHOICE_OPTIONS:
                    raise ValueError(f"choice criteria must map 1 to {MAX_CHOICE_OPTIONS} options")
            case DecisionQuestionType.SCORE:
                if not isinstance(criteria, list) or len(criteria) < 2:
                    raise ValueError("score criteria must list at least 2 ordered levels")
            case DecisionQuestionType.NOUL:
                if criteria is not None and (
                    not isinstance(criteria, dict)
                    or set(criteria) != NOUL_CRITERIA_KEYS
                    or any(value is None for value in criteria.values())
                ):
                    raise ValueError('noul criteria must be {"true": str, "false": str} or null')
        return self


class DecisionAnswer(ContractModel):
    """One answer. Only the field that matches `type` is set; the others stay null."""

    type: DecisionQuestionType
    choice: str | None = None
    score: float | None = None
    noul: Probability | None = None
    confidence: Probability | None = None
    probabilities: dict[str, Probability] = Field(default_factory=dict)
