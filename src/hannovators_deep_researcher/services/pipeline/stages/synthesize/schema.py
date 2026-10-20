"""LLM response schema for synthesis. Sources are referred to by short labels S1, S2, ..."""

from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from pydantic import Field, JsonValue

from hannovators_deep_researcher.models.base import ContractModel
from hannovators_deep_researcher.models.contracts import GradeAssessment, Recommendation
from hannovators_deep_researcher.models.enums import (
    GradeCertainty,
    RecommendationDirection,
    RecommendationStrength,
)

SYSTEM = (
    "You synthesize appraised evidence in three steps, as a skeptical reviewer. Sources are "
    "listed strongest design first (meta-analysis, systematic review, RCT, ..., web report). "
    "1) Pairwise summaries: one per intervention-versus-comparison pair and outcome (in a "
    "general brief: claim versus counter-claim), including harm and safety outcomes. Cite "
    "sources only by their labels (S1, S2, ...). Rate GRADE certainty per outcome: each source "
    "shows its GRADE start level (HIGH for randomized trials and meta-analyses of them, LOW for "
    "observational studies); start from the best design that informs the outcome, then "
    "downgrade for risk of bias, inconsistency (including opposing or null results), "
    "indirectness (an INDIRECT study counts), imprecision, and publication bias. Never rate above "
    "the start level. 2) An integrated analysis that weighs higher-level evidence more. In "
    "`opposing_evidence`, explicitly discuss the strongest opposing, harmful, or null evidence "
    "(stance OPPOSES, NULL_RESULT, or MIXED) and cite its labels in `opposing_source_labels`; "
    "if there is none, say that targeted searches found none. In `alternatives`, discuss "
    "alternative interventions, comparators, or counter-hypotheses (stance ALTERNATIVE) and cite "
    "them in `alternative_source_labels`. 3) An active-voice, directional recommendation based "
    "on the evidence only; list cost and preference considerations separately. Use only the "
    "evidence given. Reply with JSON only."
)


def _enum_text(values: Iterable[StrEnum]) -> Any:
    """A free-text field whose JSON schema still lists the expected values. At temperature 1.0
    the model sometimes writes "Moderate" or "MODERATE (downgraded)"; parsing normalizes it."""

    enum: list[JsonValue] = [str(value) for value in values]
    return Field(json_schema_extra={"enum": enum})


def _pick[E: (GradeCertainty, RecommendationDirection, RecommendationStrength)](
    text: str, enum: type[E], default: E, aliases: dict[str, E] | None = None
) -> E:
    upper = text.strip().upper().replace("-", "_").replace(" ", "_")
    for value in sorted(enum, key=lambda item: -len(item.value)):
        if upper.startswith(value.value):
            return value
    for alias, value in (aliases or {}).items():
        if upper.startswith(alias):
            return value
    return default


class GradeDraft(ContractModel):
    certainty: str = _enum_text(GradeCertainty)
    risk_of_bias: str
    inconsistency: str
    indirectness: str
    imprecision: str
    publication_bias: str

    def to_contract(self) -> GradeAssessment:
        return GradeAssessment(
            certainty=_pick(self.certainty, GradeCertainty, GradeCertainty.LOW),
            **self.model_dump(exclude={"certainty"}),
        )


class RecommendationDraft(ContractModel):
    direction: str = _enum_text(RecommendationDirection)
    strength: str = _enum_text(RecommendationStrength)
    text: str

    def to_contract(self) -> Recommendation:
        return Recommendation(
            direction=_pick(
                self.direction,
                RecommendationDirection,
                RecommendationDirection.NONE,
                {"AGAINST": RecommendationDirection.AGAINST},
            ),
            strength=_pick(
                self.strength,
                RecommendationStrength,
                RecommendationStrength.CONDITIONAL,
                {"WEAK": RecommendationStrength.CONDITIONAL},
            ),
            text=self.text,
        )


class PairwiseDraft(ContractModel):
    intervention: str
    comparison: str
    outcome: str
    summary: str
    source_labels: list[str] = Field(default_factory=list)
    grade: GradeDraft


class SynthesisDraft(ContractModel):
    pairwise_summaries: list[PairwiseDraft] = Field(default_factory=list)
    analysis: str
    opposing_evidence: str = ""
    opposing_source_labels: list[str] = Field(default_factory=list)
    alternatives: str = ""
    alternative_source_labels: list[str] = Field(default_factory=list)
    recommendation: RecommendationDraft
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
            "opposing_evidence": "Fake: S2 reported no significant difference for one outcome.",
            "opposing_source_labels": ["S2"],
            "alternatives": "Fake: no alternative intervention outperformed the intervention.",
            "alternative_source_labels": [],
            "recommendation": {
                "direction": "FOR",
                "strength": "CONDITIONAL",
                "text": "Use the intervention for eligible patients.",
            },
            "cost_and_preference_considerations": ["Cost was not assessed."],
        }
