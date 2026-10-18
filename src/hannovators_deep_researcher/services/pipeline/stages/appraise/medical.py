"""MEDICAL appraisal: M-criteria match vs PICOTS, RoB 2 from the abstract, METRIC claims."""

import json
from typing import Any, Literal

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel, Probability
from hannovators_deep_researcher.models.contracts import PicotsDecomposition, Rob2Assessment
from hannovators_deep_researcher.models.enums import (
    ClaimArm,
    ClaimKind,
    ClaimVerdict,
    Directness,
    RejectionCode,
    RobJudgement,
)
from hannovators_deep_researcher.services.pipeline.stages.appraise.common import (
    ABSTRACT_ONLY,
    ClaimDraft,
    SourceAppraisal,
    checked_verdict,
)

RobDomainName = Literal[
    "randomization", "deviations", "missing_data", "measurement", "selective_reporting"
]
_ROB_ORDER = {RobJudgement.LOW: 0, RobJudgement.SOME_CONCERNS: 1, RobJudgement.HIGH: 2}

SYSTEM = (
    "You appraise one clinical study for a systematic review, using only its title and abstract. "
    "1) For each PICO criterion (P, I, C, O), say whether the study matches the review PICOTS. "
    "2) Judge Cochrane RoB 2 for all five domains (randomization, deviations, missing_data, "
    "measurement, selective_reporting) as LOW, SOME_CONCERNS, or HIGH; the abstract gives limited "
    "detail, so prefer SOME_CONCERNS when it is silent. 3) Extract key numeric results as metrics "
    "(events/total per arm, effect estimates, confidence intervals). Each metric `quote` MUST be "
    "copied verbatim from the abstract. Never paraphrase a quote. Reply with JSON only."
)


class CriterionMatch(ContractModel):
    criterion: Literal["P", "I", "C", "O"]
    matched: bool
    rationale: str


class RobDomainJudgement(ContractModel):
    domain: RobDomainName
    judgement: RobJudgement
    rationale: str


class MetricDraft(ContractModel):
    label: str
    text: str
    quote: str
    outcome: str | None = None
    arm: ClaimArm | None = None
    confidence: Probability = 0.5


class MedicalAppraisal(ContractModel):
    study_design: str | None = None
    criteria: list[CriterionMatch] = Field(default_factory=list)
    rob2: list[RobDomainJudgement] = Field(default_factory=list)
    metrics: list[MetricDraft] = Field(default_factory=list)
    explanation: str

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "study_design": "randomized controlled trial",
            "criteria": [
                {"criterion": name, "matched": name != "C", "rationale": "Fake match."}
                for name in ("P", "I", "C", "O")
            ],
            "rob2": [
                {"domain": domain, "judgement": "LOW", "rationale": "Fake judgement."}
                for domain in (
                    "randomization",
                    "deviations",
                    "missing_data",
                    "measurement",
                    "selective_reporting",
                )
            ],
            "metrics": [
                {
                    "label": "Primary outcome",
                    "text": "Fewer events with the intervention.",
                    "quote": "randomized",
                    "outcome": "primary outcome",
                    "arm": "INTERVENTION",
                    "confidence": 0.7,
                }
            ],
            "explanation": "Fake appraisal from the abstract.",
        }


def user_prompt(decomposition: PicotsDecomposition, title: str, abstract: str) -> str:
    return (
        f"Review PICOTS:\n{decomposition.model_dump_json(indent=1)}\n\n"
        f"Study title: {title}\n\nAbstract:\n{abstract}"
    )


def m_score(criteria: list[CriterionMatch]) -> int:
    return len({match.criterion for match in criteria if match.matched})


def overall_rob(judgements: list[RobJudgement]) -> RobJudgement:
    """RoB 2 overall equals the worst domain; no domains means SOME_CONCERNS."""

    return max(judgements, key=_ROB_ORDER.__getitem__, default=RobJudgement.SOME_CONCERNS)


def evaluate(
    source_id: str, abstract: str, reply: MedicalAppraisal, threshold: int
) -> SourceAppraisal:
    score = m_score(reply.criteria)
    domains: dict[str, RobJudgement] = {item.domain: item.judgement for item in reply.rob2}
    overall = overall_rob(list(domains.values()))
    claims = [
        ClaimDraft(
            kind=ClaimKind.METRIC,
            label=metric.label,
            text=metric.text,
            quote=metric.quote,
            verdict=checked_verdict(ClaimVerdict.SUPPORTED, metric.quote, abstract),
            confidence=metric.confidence,
            outcome=metric.outcome,
            arm=metric.arm,
        )
        for metric in reply.metrics
    ]
    eligible = score >= threshold
    verified = sum(claim.verdict != ClaimVerdict.UNVERIFIED for claim in claims)
    appraisal = {
        "basis": ABSTRACT_ONLY,
        "criteria": [item.model_dump(mode="json") for item in reply.criteria],
        "rob2_rationale": {
            item.domain: f"{ABSTRACT_ONLY}: {item.rationale}" for item in reply.rob2
        },
        "explanation": reply.explanation,
    }
    return SourceAppraisal(
        source_id=source_id,
        eligible=eligible,
        rank=score * 10 + (2 - _ROB_ORDER[overall]) * 3 + verified,
        explanation=f"M={score}/{threshold} required; RoB 2 overall {overall}. {reply.explanation}",
        rejection_code=None if eligible else RejectionCode.M_BELOW_THRESHOLD,
        m_score=score,
        directness=(Directness.INDIRECT if score == threshold else Directness.DIRECT)
        if eligible
        else None,
        study_design=reply.study_design,
        rob2_json=Rob2Assessment(domains=domains, overall=overall).model_dump_json(),
        appraisal_json=json.dumps(appraisal),
        claims=claims,
    )
