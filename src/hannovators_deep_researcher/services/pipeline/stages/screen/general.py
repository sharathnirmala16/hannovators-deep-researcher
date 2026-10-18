"""GENERAL screening questions: entity, claim, and credibility votes."""

from hannovators_deep_researcher.models.contracts import ScopeDecomposition
from hannovators_deep_researcher.models.enums import RejectionCode
from hannovators_deep_researcher.services.pipeline.stages.screen.questions import (
    EXCLUSION_KEY,
    RELEVANCE,
    RELEVANCE_KEY,
    exclusion,
    vote,
)

VOTE_KEYS = ("entity", "claim", "credibility")

QUESTIONS = {
    RELEVANCE_KEY: RELEVANCE,
    "entity": vote("Is the record about one of the scope entities or counter-hypotheses?"),
    "claim": vote("Does the record give evidence for or against one of the scope claims?"),
    "credibility": vote("Is the record from a credible, identifiable source with evidence?"),
    EXCLUSION_KEY: exclusion(
        {
            RejectionCode.OFF_TOPIC: "About a different entity or question",
            RejectionCode.LOW_CREDIBILITY: "Anonymous, promotional, or unsupported content",
            RejectionCode.REVIEW_OR_EDITORIAL: "Opinion piece with no new evidence",
        }
    ),
}


def summarize(decomposition: ScopeDecomposition) -> str:
    return "\n".join(
        [
            f"Entities: {'; '.join(decomposition.entities)}",
            f"Claims: {'; '.join(decomposition.claims)}",
            f"Metrics: {'; '.join(decomposition.metrics)}",
            f"Counter-hypotheses: {'; '.join(decomposition.counter_hypotheses)}",
        ]
    )
