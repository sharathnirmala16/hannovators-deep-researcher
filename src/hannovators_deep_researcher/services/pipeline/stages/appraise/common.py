"""Shared appraisal pieces: quote verification and the per-source result both modes produce."""

from dataclasses import dataclass, field

from hannovators_deep_researcher.models.enums import (
    ClaimArm,
    ClaimKind,
    ClaimVerdict,
    Directness,
    EvidenceLevel,
    EvidenceStance,
    RejectionCode,
)

EVIDENCE_PROMPT = (
    "Also classify the source: `evidence_level` is its study design on the evidence hierarchy "
    "(META_ANALYSIS, SYSTEMATIC_REVIEW, RCT, NON_RANDOMIZED_TRIAL, COHORT, CASE_CONTROL, "
    "CROSS_SECTIONAL, CASE_SERIES, GUIDELINE, NARRATIVE_REVIEW, PRECLINICAL, WEB_REPORT, OTHER); "
    "`stance` is what it concludes about the research question (SUPPORTS, OPPOSES for harm or "
    "worse outcomes, NULL_RESULT for no significant effect or a failed/stopped trial, MIXED, "
    "ALTERNATIVE when it mainly studies another option, UNCLEAR). Report harms and null results "
    "as faithfully as benefits."
)

ABSTRACT_ONLY = "abstract-only"


def _normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def quote_in_text(quote: str | None, text: str | None) -> bool:
    """True when the quote appears verbatim in the text, ignoring case and whitespace runs."""

    if not quote or not quote.strip() or not text:
        return False
    return _normalize(quote) in _normalize(text)


def checked_verdict(verdict: ClaimVerdict, quote: str | None, text: str | None) -> ClaimVerdict:
    """Keep the model's verdict only when its quote is found in the text."""

    return verdict if quote_in_text(quote, text) else ClaimVerdict.UNVERIFIED


@dataclass(frozen=True)
class ClaimDraft:
    kind: ClaimKind
    label: str
    text: str
    quote: str | None
    verdict: ClaimVerdict
    confidence: float | None
    outcome: str | None = None
    arm: ClaimArm | None = None


@dataclass
class SourceAppraisal:
    """One appraised source. `rank` orders eligible sources within one evidence level; higher
    is better. `evidence_level` and `stance` are the appraisal model's reading of the source."""

    source_id: str
    eligible: bool
    rank: float
    explanation: str
    rejection_code: RejectionCode | None = None
    m_score: int | None = None
    directness: Directness | None = None
    study_design: str | None = None
    rob2_json: str | None = None
    appraisal_json: str = "{}"
    claims: list[ClaimDraft] = field(default_factory=list)
    evidence_level: EvidenceLevel | None = None
    stance: EvidenceStance | None = None
