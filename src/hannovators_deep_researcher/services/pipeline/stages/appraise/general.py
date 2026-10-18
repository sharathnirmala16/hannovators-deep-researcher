"""GENERAL appraisal: claim verification, credibility, conflicts of interest, contradictions."""

import json
from typing import Any

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel, Probability
from hannovators_deep_researcher.models.contracts import ScopeDecomposition
from hannovators_deep_researcher.models.enums import ClaimKind, ClaimVerdict, RejectionCode
from hannovators_deep_researcher.services.pipeline.stages.appraise.common import (
    ABSTRACT_ONLY,
    ClaimDraft,
    SourceAppraisal,
    checked_verdict,
)

MIN_CREDIBILITY = 0.3

SYSTEM = (
    "You appraise one source for a research brief, using only its title and summary text. "
    "Extract the claims that bear on the brief's scope. For each claim give a verdict "
    "(SUPPORTED, CONTRADICTED, MIXED, UNVERIFIED) against the scope claims, a confidence 0..1, and "
    "a `quote` copied verbatim from the source text. Never paraphrase a quote. Rate the source "
    "credibility 0..1, flag a conflict of interest, and list contradictions. Reply with JSON only."
)


class ClaimCheck(ContractModel):
    label: str
    text: str
    quote: str
    verdict: ClaimVerdict
    confidence: Probability


class GeneralAppraisal(ContractModel):
    credibility: Probability
    relevance: Probability
    conflict_of_interest: bool = False
    claims: list[ClaimCheck] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    explanation: str

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "credibility": 0.7,
            "relevance": 0.8,
            "conflict_of_interest": False,
            "claims": [
                {
                    "label": "Main claim",
                    "text": "The source supports the main claim.",
                    "quote": "the",
                    "verdict": "SUPPORTED",
                    "confidence": 0.7,
                }
            ],
            "contradictions": [],
            "explanation": "Fake appraisal from the summary.",
        }


def user_prompt(decomposition: ScopeDecomposition, title: str, text: str) -> str:
    return (
        f"Research scope:\n{decomposition.model_dump_json(indent=1)}\n\n"
        f"Source title: {title}\n\nSource text:\n{text}"
    )


def evaluate(source_id: str, text: str, reply: GeneralAppraisal) -> SourceAppraisal:
    claims = [
        ClaimDraft(
            kind=ClaimKind.CLAIM,
            label=claim.label,
            text=claim.text,
            quote=claim.quote,
            verdict=checked_verdict(claim.verdict, claim.quote, text),
            confidence=claim.confidence,
        )
        for claim in reply.claims
    ]
    eligible = reply.credibility >= MIN_CREDIBILITY
    appraisal = {
        "basis": ABSTRACT_ONLY,
        "credibility": reply.credibility,
        "relevance": reply.relevance,
        "conflict_of_interest": reply.conflict_of_interest,
        "contradictions": reply.contradictions,
        "explanation": reply.explanation,
    }
    return SourceAppraisal(
        source_id=source_id,
        eligible=eligible,
        rank=reply.credibility * reply.relevance,
        explanation=f"Credibility {reply.credibility:.2f}. {reply.explanation}",
        rejection_code=None if eligible else RejectionCode.LOW_CREDIBILITY,
        appraisal_json=json.dumps(appraisal),
        claims=claims,
    )
