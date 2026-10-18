"""LLM response schema for synthesis. Sources are referred to by short labels S1, S2, ..."""

from typing import Any

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel
from hannovators_deep_researcher.models.contracts import GradeAssessment, Recommendation

SYSTEM = (
    "You synthesize appraised evidence in three steps. 1) Pairwise summaries: one per "
    "intervention-versus-comparison pair and outcome (in a general brief: claim versus "
    "counter-claim). Cite sources only by their labels (S1, S2, ...). Rate GRADE certainty per "
    "outcome: start HIGH for randomized trials and LOW for observational studies, then "
    "downgrade for risk of bias, inconsistency, indirectness (an INDIRECT study counts), "
    "imprecision, and publication bias. Never rate above the start level. 2) An integrated "
    "analysis. 3) An active-voice, directional recommendation based on the evidence only; "
    "list cost and preference considerations separately. Use only the evidence given. "
    "Reply with JSON only."
)


class PairwiseDraft(ContractModel):
    intervention: str
    comparison: str
    outcome: str
    summary: str
    source_labels: list[str] = Field(default_factory=list)
    grade: GradeAssessment


class SynthesisDraft(ContractModel):
    pairwise_summaries: list[PairwiseDraft] = Field(default_factory=list)
    analysis: str
    recommendation: Recommendation
    cost_and_preference_considerations: list[str] = Field(default_factory=list)

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "pairwise_summaries": [
                {
                    "intervention": "Intervention",
                    "comparison": "Comparison",
                    "outcome": "Primary outcome",
                    "summary": "The intervention reduced events compared with the comparison.",
                    "source_labels": ["S1", "S2"],
                    "grade": {
                        "certainty": "MODERATE",
                        "risk_of_bias": "Some concerns in one trial.",
                        "inconsistency": "Not serious.",
                        "indirectness": "Not serious.",
                        "imprecision": "Serious: few events.",
                        "publication_bias": "Undetected.",
                    },
                }
            ],
            "analysis": "Fake analysis: the appraised studies point in the same direction.",
            "recommendation": {
                "direction": "FOR",
                "strength": "CONDITIONAL",
                "text": "Use the intervention for eligible patients.",
            },
            "cost_and_preference_considerations": ["Cost was not assessed."],
        }
