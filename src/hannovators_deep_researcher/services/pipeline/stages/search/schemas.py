"""LLM response schemas for `search`. Each defines `fake_example()` for PROVIDER_MODE=fake."""

from typing import Any

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel
from hannovators_deep_researcher.models.enums import SearchIntent


class IntentQueryPlan(ContractModel):
    """Queries per search intent. NEGATIVE, ALTERNATIVE, and SAFETY always run next to CORE."""

    core: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)
    alternative: list[str] = Field(default_factory=list)
    safety: list[str] = Field(default_factory=list)

    def by_intent(self) -> dict[SearchIntent, list[str]]:
        return {
            SearchIntent.CORE: self.core,
            SearchIntent.NEGATIVE: self.negative,
            SearchIntent.ALTERNATIVE: self.alternative,
            SearchIntent.SAFETY: self.safety,
        }


class MedicalQueryPlan(IntentQueryPlan):
    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "core": [
                "SGLT2 inhibitors heart failure reduced ejection fraction",
                "SGLT2 inhibitor cardiovascular death hospitalization heart failure",
                "SGLT2 inhibitors placebo heart failure outcomes",
            ],
            "negative": [
                "SGLT2 inhibitors heart failure no significant difference terminated",
            ],
            "alternative": [
                "mineralocorticoid receptor antagonist heart failure reduced ejection fraction",
            ],
            "safety": ["SGLT2 inhibitors heart failure adverse events ketoacidosis"],
        }


class GeneralQueryPlan(IntentQueryPlan):
    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "core": [
                "Kestrel Ionics KI-175 sodium-ion cell energy density",
                "Kestrel Ionics gigafactory 2027 production start",
                "sodium-ion battery 175 Wh/kg volume production",
            ],
            "negative": ["Kestrel Ionics KI-175 independent test lower energy density"],
            "alternative": ["LFP cells pack energy density versus sodium-ion"],
            "safety": ["Kestrel Ionics sodium-ion cell safety recall incident"],
        }


class QueryRewrite(ContractModel):
    query: str
    note: str

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "query": "SGLT2 inhibitors heart failure",
            "note": "Dropped secondary terms to broaden the query.",
        }
