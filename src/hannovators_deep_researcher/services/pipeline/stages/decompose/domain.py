"""Domain detection for AUTO mode: one Jev `choice`, with a keyword fallback."""

import re

from hannovators_deep_researcher.models.decisions import DecisionQuestion
from hannovators_deep_researcher.models.enums import DecisionQuestionType, DomainMode
from hannovators_deep_researcher.models.ports import DecisionModel

DOMAIN_QUESTION = DecisionQuestion(
    type=DecisionQuestionType.CHOICE,
    instructions="Which research domain does this question belong to?",
    criteria={
        DomainMode.MEDICAL: "Clinical or health research: patients, treatments, diagnosis, trials",
        DomainMode.GENERAL: "Anything else: business, technology, policy, science claims",
    },
)

MEDICAL_KEYWORDS = frozenset(
    {
        "adult",
        "adults",
        "children",
        "clinical",
        "disease",
        "dose",
        "drug",
        "efficacy",
        "hospitalization",
        "infant",
        "inhibitor",
        "inhibitors",
        "mortality",
        "patient",
        "patients",
        "placebo",
        "randomized",
        "symptom",
        "symptoms",
        "therapy",
        "treatment",
        "trial",
        "vaccine",
    }
)
_WORD = re.compile(r"[a-z0-9]+")


def keyword_domain(question: str) -> DomainMode:
    words = set(_WORD.findall(question.lower()))
    return DomainMode.MEDICAL if words & MEDICAL_KEYWORDS else DomainMode.GENERAL


async def detect_domain(decisions: DecisionModel, question: str) -> tuple[DomainMode, str]:
    """Return the domain and the method (`jev` or `keywords`) that decided it."""

    try:
        answers = await decisions.evaluate(question, {"domain": DOMAIN_QUESTION})
        return DomainMode(answers["domain"].choice or ""), "jev"
    except Exception:
        return keyword_domain(question), "keywords"
