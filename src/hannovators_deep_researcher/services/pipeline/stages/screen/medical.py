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
    "intervention": vote("Does the study test the review intervention against a comparator?"),
    "design": vote("Is the study design eligible (for example a randomized controlled trial)?"),
    EXCLUSION_KEY: exclusion(
        {
            RejectionCode.ANIMAL_STUDY: "Animal or in-vitro study",
            RejectionCode.REVIEW_OR_EDITORIAL: "Review, editorial, comment, or letter",
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
