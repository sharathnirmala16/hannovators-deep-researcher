"""MEDICAL screening questions: population, intervention, and design votes."""

from hannovators_deep_researcher.models.contracts import PicotsDecomposition
from hannovators_deep_researcher.models.enums import RejectionCode
from hannovators_deep_researcher.services.pipeline.stages.screen.questions import (
    EXCLUSION_KEY,
    RELEVANCE,
    RELEVANCE_KEY,
    exclusion,
    vote,
)

VOTE_KEYS = ("population", "intervention", "design")

QUESTIONS = {
    RELEVANCE_KEY: RELEVANCE,
    "population": vote("Does the study population match the review population?"),
    "intervention": vote(
        "Does the study test the review intervention, or one of the review comparators, "
        "against a comparator (benefit or harm)?"
    ),
    "design": vote(
        "Is the design eligible: a systematic review or meta-analysis, a randomized trial, or "
        "a controlled observational study of human patients?"
    ),
    EXCLUSION_KEY: exclusion(
        {
            RejectionCode.ANIMAL_STUDY: "Animal or in-vitro study",
            RejectionCode.REVIEW_OR_EDITORIAL: (
                "Narrative review, editorial, comment, or letter (not a systematic review)"
            ),
            RejectionCode.OFF_TOPIC: "Different population, intervention, or question",
        }
    ),
}


def summarize(decomposition: PicotsDecomposition) -> str:
    return "\n".join(
        [
            f"Population: {decomposition.population}",
            f"Interventions: {'; '.join(decomposition.interventions)}",
            f"Comparisons: {'; '.join(decomposition.comparisons) or 'any'}",
            f"Outcomes: {'; '.join(decomposition.outcomes)}",
            f"Study designs: {'; '.join(decomposition.study_designs) or 'any'}",
        ]
    )
