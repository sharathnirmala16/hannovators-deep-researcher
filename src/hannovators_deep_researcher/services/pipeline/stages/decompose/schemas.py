"""LLM response schemas for `decompose`. Each defines `fake_example()` for PROVIDER_MODE=fake."""

from typing import Any

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel
from hannovators_deep_researcher.models.contracts import PicotsDecomposition, ScopeDecomposition

_FAKE_PICOTS: dict[str, Any] = {
    "population": "Adults with heart failure with reduced ejection fraction",
    "interventions": ["SGLT2 inhibitors"],
    "comparisons": ["placebo"],
    "outcomes": ["cardiovascular death", "hospitalization for heart failure"],
    "timing": "At least 12 months of follow-up",
    "study_designs": ["randomized controlled trial"],
    "ic_pairs": [{"intervention": "SGLT2 inhibitors", "comparison": "placebo"}],
}

_FAKE_SCOPE: dict[str, Any] = {
    "entities": ["Kestrel Ionics", "KI-175 sodium-ion cell"],
    "claims": [
        "KI-175 reaches 175 Wh/kg in volume production",
        "The gigafactory starts production in 2027",
    ],
    "metrics": ["gravimetric energy density (Wh/kg)", "production start date"],
    "time_horizon": "2025 to 2027",
    "counter_hypotheses": ["175 Wh/kg holds only for lab cells, not volume production"],
}


class PicotsDraft(PicotsDecomposition):
    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return dict(_FAKE_PICOTS)


class ScopeDraft(ScopeDecomposition):
    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return dict(_FAKE_SCOPE)


class PicotsRevision(ContractModel):
    """Critique of the draft, then the revised decomposition."""

    critique: list[str] = Field(default_factory=list)
    decomposition: PicotsDraft

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "critique": ["Outcomes are specific; no change needed."],
            "decomposition": PicotsDraft.fake_example(),
        }


class ScopeRevision(ContractModel):
    critique: list[str] = Field(default_factory=list)
    decomposition: ScopeDraft

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "critique": ["Added a counter-hypothesis about lab versus production cells."],
            "decomposition": ScopeDraft.fake_example(),
        }
