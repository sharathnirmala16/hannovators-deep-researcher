"""LLM response schemas for `search`. Each defines `fake_example()` for PROVIDER_MODE=fake."""

from typing import Any

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel


class MedicalQueryPlan(ContractModel):
    queries: list[str] = Field(default_factory=list)

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "queries": [
                "SGLT2 inhibitors heart failure reduced ejection fraction",
                "SGLT2 inhibitor cardiovascular death hospitalization heart failure",
                "SGLT2 inhibitors placebo heart failure outcomes",
            ]
        }


class GeneralQueryPlan(ContractModel):
    queries: list[str] = Field(default_factory=list)

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "queries": [
                "Kestrel Ionics KI-175 sodium-ion cell energy density",
                "Kestrel Ionics gigafactory 2027 production start",
                "sodium-ion battery 175 Wh/kg volume production",
            ]
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
