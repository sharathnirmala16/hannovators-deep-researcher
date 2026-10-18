"""Shared Jev question builders for screening."""

from hannovators_deep_researcher.models.decisions import DecisionQuestion
from hannovators_deep_researcher.models.enums import DecisionQuestionType

RELEVANCE_KEY = "relevance"
EXCLUSION_KEY = "exclusion"
NO_EXCLUSION = "NONE"

RELEVANCE = DecisionQuestion(
    type=DecisionQuestionType.SCORE,
    instructions="How relevant is this record to the research scope above?",
    criteria=[
        "Not relevant",
        "Slightly relevant",
        "Moderately relevant",
        "Highly relevant",
        "Directly answers the research question",
    ],
)
MAX_RELEVANCE = 4.0


def vote(instructions: str) -> DecisionQuestion:
    return DecisionQuestion(
        type=DecisionQuestionType.NOUL,
        instructions=instructions,
        criteria={"true": "Yes, it matches", "false": "No, or the record does not say"},
    )


def exclusion(options: dict[str, str | None]) -> DecisionQuestion:
    return DecisionQuestion(
        type=DecisionQuestionType.CHOICE,
        instructions="Which exclusion reason applies to this record, if any?",
        criteria={NO_EXCLUSION: "No exclusion reason applies", **options},
    )
