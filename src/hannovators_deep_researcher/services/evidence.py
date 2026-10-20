"""Evidence quality: study-design level on the evidence hierarchy and stance toward the question.

`heuristic_level()` reads PubMed publication types and title/abstract keywords. A decisive
signal (publication type or a title keyword) is final; otherwise the guess is tentative and a
Jev `choice` over the `EvidenceLevel` values decides. `classify_stance()` asks Jev whether a
record supports, opposes, finds no effect for, or proposes an alternative to the question.
Screening embeds the same questions in its per-candidate request, so it reuses the builders.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from hannovators_deep_researcher.models.decisions import DecisionAnswer, DecisionQuestion
from hannovators_deep_researcher.models.enums import (
    EVIDENCE_RANK,
    DecisionQuestionType,
    DomainMode,
    EvidenceLevel,
    EvidenceStance,
    GradeCertainty,
    SourceOrigin,
)
from hannovators_deep_researcher.models.ports import DecisionModel

EVIDENCE_KEY = "evidence_level"
STANCE_KEY = "stance"
MAX_STATE_ABSTRACT = 6_000
UNKNOWN_RANK = max(EVIDENCE_RANK.values()) + 1

OPPOSING_STANCES = frozenset({EvidenceStance.OPPOSES, EvidenceStance.NULL_RESULT})
"""Disconfirming evidence: harm, worse outcomes, no effect, or failed trials."""
CONTRARIAN_STANCES = OPPOSING_STANCES | {EvidenceStance.MIXED, EvidenceStance.ALTERNATIVE}
"""Evidence that is not plain support: screening and appraisal reserve room for it."""

LEVEL_DESCRIPTIONS: dict[str, str | None] = {
    EvidenceLevel.META_ANALYSIS: "Meta-analysis or pooled analysis of several studies",
    EvidenceLevel.SYSTEMATIC_REVIEW: "Systematic review without a quantitative meta-analysis",
    EvidenceLevel.RCT: "Randomized controlled trial, or a pre-specified/post hoc analysis of one",
    EvidenceLevel.NON_RANDOMIZED_TRIAL: "Interventional trial without randomization",
    EvidenceLevel.COHORT: "Prospective or retrospective cohort, registry, or real-world study",
    EvidenceLevel.CASE_CONTROL: "Case-control study",
    EvidenceLevel.CROSS_SECTIONAL: "Cross-sectional survey or prevalence study",
    EvidenceLevel.CASE_SERIES: "Case report or case series",
    EvidenceLevel.GUIDELINE: "Clinical practice guideline, consensus statement, or regulator label",
    EvidenceLevel.NARRATIVE_REVIEW: "Narrative review, editorial, or expert opinion",
    EvidenceLevel.PRECLINICAL: "Animal, cell, or in-vitro study",
    EvidenceLevel.WEB_REPORT: "News, press release, blog, or other web report",
    EvidenceLevel.OTHER: "Protocol, methods paper, or anything else",
}

EVIDENCE_QUESTION = DecisionQuestion(
    type=DecisionQuestionType.CHOICE,
    instructions="What is the study design of this record on the evidence hierarchy?",
    criteria=LEVEL_DESCRIPTIONS,
)

_MEDICAL_STANCES: dict[str, str | None] = {
    EvidenceStance.SUPPORTS: "Finds benefit of the review intervention on the review outcomes",
    EvidenceStance.OPPOSES: "Finds harm, worse outcomes, or evidence against the intervention",
    EvidenceStance.NULL_RESULT: "Finds no significant effect, futility, or a failed/stopped trial",
    EvidenceStance.MIXED: "Benefit on some outcomes but harm or no effect on others",
    EvidenceStance.ALTERNATIVE: "Tests a different intervention, not the review intervention",
    EvidenceStance.UNCLEAR: "Reports no directional result for the review question",
}
_GENERAL_STANCES: dict[str, str | None] = {
    EvidenceStance.SUPPORTS: "Gives evidence that the scope claims are true",
    EvidenceStance.OPPOSES: "Gives evidence that the scope claims are false or overstated",
    EvidenceStance.NULL_RESULT: "Finds no measurable effect or a failed attempt",
    EvidenceStance.MIXED: "Supports some claims and contradicts others",
    EvidenceStance.ALTERNATIVE: "Argues for a counter-hypothesis or a competing explanation",
    EvidenceStance.UNCLEAR: "Takes no position on the scope claims",
}


def stance_question(mode: DomainMode) -> DecisionQuestion:
    criteria = _MEDICAL_STANCES if mode is DomainMode.MEDICAL else _GENERAL_STANCES
    return DecisionQuestion(
        type=DecisionQuestionType.CHOICE,
        instructions=(
            "Relative to the research scope above, what does this record conclude? When it "
            "studies the scope's intervention or claims, judge its result: SUPPORTS, OPPOSES, "
            "NULL_RESULT, or MIXED. Pick OPPOSES or NULL_RESULT whenever it reports harm, no "
            "benefit, or failure. Pick ALTERNATIVE only when it tests something else."
        ),
        criteria=criteria,
    )


# --- Heuristic study-design classification ------------------------------------------


@dataclass(frozen=True, slots=True)
class LevelGuess:
    """A heuristic level. `decisive` guesses skip Jev; tentative ones are only a fallback."""

    level: EvidenceLevel | None
    method: str
    decisive: bool


_PUBLICATION_TYPES: tuple[tuple[str, EvidenceLevel], ...] = (
    ("meta-analysis", EvidenceLevel.META_ANALYSIS),
    ("systematic review", EvidenceLevel.SYSTEMATIC_REVIEW),
    ("randomized controlled trial", EvidenceLevel.RCT),
    ("equivalence trial", EvidenceLevel.RCT),
    ("pragmatic clinical trial", EvidenceLevel.RCT),
    ("practice guideline", EvidenceLevel.GUIDELINE),
    ("guideline", EvidenceLevel.GUIDELINE),
    ("consensus development conference", EvidenceLevel.GUIDELINE),
    ("case reports", EvidenceLevel.CASE_SERIES),
    ("editorial", EvidenceLevel.NARRATIVE_REVIEW),
    ("comment", EvidenceLevel.NARRATIVE_REVIEW),
    ("letter", EvidenceLevel.NARRATIVE_REVIEW),
)
_TENTATIVE_TYPES: tuple[tuple[str, EvidenceLevel], ...] = (
    ("controlled clinical trial", EvidenceLevel.NON_RANDOMIZED_TRIAL),
    ("clinical trial", EvidenceLevel.NON_RANDOMIZED_TRIAL),
    ("observational study", EvidenceLevel.COHORT),
    ("review", EvidenceLevel.NARRATIVE_REVIEW),
)


def _pattern(*words: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(words) + r")", re.IGNORECASE)


_KEYWORD_TABLE: tuple[tuple[EvidenceLevel, tuple[str, ...]], ...] = (
    (EvidenceLevel.META_ANALYSIS, (r"meta-?\s?analys", r"network meta", r"pooled analysis")),
    (EvidenceLevel.SYSTEMATIC_REVIEW, (r"systematic (?:literature )?review", r"umbrella review")),
    (
        EvidenceLevel.GUIDELINE,
        (
            r"guideline",
            r"consensus statement",
            r"kdigo",
            r"position statement",
            r"prescribing information",
        ),
    ),
    (
        EvidenceLevel.RCT,
        (
            r"randomi[sz]ed",
            r"double-blind",
            r"placebo-controlled",
            r"post hoc analysis of",
            r"pre-?specified analysis",
        ),
    ),
    (EvidenceLevel.CASE_CONTROL, (r"case-control", r"case control")),
    (EvidenceLevel.CROSS_SECTIONAL, (r"cross-sectional",)),
    (
        EvidenceLevel.COHORT,
        (
            r"cohort",
            r"registry",
            r"retrospective",
            r"real-world",
            r"observational",
            r"target trial emulation",
        ),
    ),
    (EvidenceLevel.CASE_SERIES, (r"case report", r"case series")),
    (
        EvidenceLevel.PRECLINICAL,
        (r"mice", r"murine", r"rats?\b", r"in vitro", r"animal model", r"cell line"),
    ),
    (
        EvidenceLevel.NON_RANDOMIZED_TRIAL,
        (r"single-arm", r"open-label trial", r"phase (?:1|2|i|ii) (?:trial|study)"),
    ),
    (EvidenceLevel.NARRATIVE_REVIEW, (r"review",)),
)
_KEYWORDS: tuple[tuple[re.Pattern[str], EvidenceLevel], ...] = tuple(
    (_pattern(*words), level) for level, words in _KEYWORD_TABLE
)


def _keyword_level(text: str) -> EvidenceLevel | None:
    for pattern, level in _KEYWORDS:
        if pattern.search(text):
            return level
    return None


def _type_level(
    publication_types: Iterable[str], table: Sequence[tuple[str, EvidenceLevel]]
) -> EvidenceLevel | None:
    lowered = [item.strip().lower() for item in publication_types]
    best: EvidenceLevel | None = None
    for name, level in table:
        if any(item == name or item.startswith(f"{name},") for item in lowered) and (
            best is None or EVIDENCE_RANK[level] < EVIDENCE_RANK[best]
        ):
            best = level
    return best


def heuristic_level(
    *,
    title: str,
    abstract: str | None,
    publication_types: Sequence[str] = (),
    origin: SourceOrigin | str | None = None,
) -> LevelGuess:
    """Publication types and title keywords decide; abstract keywords only suggest."""

    by_type = _type_level(publication_types, _PUBLICATION_TYPES)
    if by_type is not None:
        return LevelGuess(by_type, "publication_type", True)
    by_title = _keyword_level(title)
    if by_title is not None and by_title is not EvidenceLevel.NARRATIVE_REVIEW:
        return LevelGuess(by_title, "title_keywords", True)
    tentative = (
        _type_level(publication_types, _TENTATIVE_TYPES)
        or _keyword_level((abstract or "")[:MAX_STATE_ABSTRACT])
        or by_title
    )
    if tentative is not None:
        return LevelGuess(tentative, "keywords", False)
    if origin == SourceOrigin.WEB:
        return LevelGuess(EvidenceLevel.WEB_REPORT, "origin", False)
    return LevelGuess(None, "none", False)


def level_from_design_text(text: str | None) -> EvidenceLevel | None:
    """Map a free-text study design (for example from the appraisal model) to a level."""

    return _keyword_level(text or "") if text else None


# --- Jev answers -------------------------------------------------------------------


def parse_level(value: object) -> EvidenceLevel | None:
    try:
        return EvidenceLevel(str(value)) if value else None
    except ValueError:
        return None


def parse_stance(value: object) -> EvidenceStance | None:
    try:
        return EvidenceStance(str(value)) if value else None
    except ValueError:
        return None


def level_from_answer(
    answer: DecisionAnswer | None, guess: LevelGuess
) -> tuple[EvidenceLevel, str]:
    """Jev's choice when it parses; else the heuristic guess; else OTHER."""

    chosen = parse_level(answer.choice) if answer is not None else None
    if chosen is not None:
        return chosen, "jev"
    return guess.level or EvidenceLevel.OTHER, guess.method


_NULL_PATTERN = _pattern(
    r"no significant (?:difference|effect|benefit|reduction)",
    r"did not (?:significantly )?(?:reduce|improve|lower|differ)",
    r"not significantly",
    r"futility",
    r"terminated early",
    r"stopped early",
    r"no benefit",
    r"failed to",
)
_HARM_PATTERN = _pattern(
    r"increased (?:the )?risk", r"higher (?:risk|incidence|rate) of", r"harm", r"worse"
)


def keyword_stance(text: str) -> EvidenceStance:
    """Fallback stance when Jev is unavailable: null and harm phrases, else UNCLEAR."""

    if _NULL_PATTERN.search(text):
        return EvidenceStance.NULL_RESULT
    if _HARM_PATTERN.search(text):
        return EvidenceStance.OPPOSES
    return EvidenceStance.UNCLEAR


def stance_from_answer(answer: DecisionAnswer | None, text: str) -> tuple[EvidenceStance, str]:
    chosen = parse_stance(answer.choice) if answer is not None else None
    if chosen is not None:
        return chosen, "jev"
    return keyword_stance(text), "keywords"


# --- Standalone classifiers ----------------------------------------------------------


def record_state(scope: str, title: str, abstract: str | None) -> str:
    body = (abstract or "No abstract available.")[:MAX_STATE_ABSTRACT]
    return f"Research scope:\n{scope}\n\nRecord title: {title}\n\nAbstract:\n{body}"


async def classify_evidence(
    decisions: DecisionModel | None,
    *,
    title: str,
    abstract: str | None,
    publication_types: Sequence[str] = (),
    origin: SourceOrigin | str | None = None,
) -> tuple[EvidenceLevel, str]:
    """Return `(level, method)`. Jev is asked only when the heuristics are not decisive."""

    guess = heuristic_level(
        title=title, abstract=abstract, publication_types=publication_types, origin=origin
    )
    if guess.decisive and guess.level is not None:
        return guess.level, guess.method
    if decisions is None:
        return guess.level or EvidenceLevel.OTHER, guess.method
    types = f"\n\nPublication types: {', '.join(publication_types)}" if publication_types else ""
    try:
        answers = await decisions.evaluate(
            record_state("Classify the study design.", title, abstract) + types,
            {EVIDENCE_KEY: EVIDENCE_QUESTION},
        )
    except Exception:
        return guess.level or EvidenceLevel.OTHER, guess.method
    return level_from_answer(answers.get(EVIDENCE_KEY), guess)


async def classify_stance(
    decisions: DecisionModel | None,
    *,
    mode: DomainMode,
    scope: str,
    title: str,
    abstract: str | None,
) -> tuple[EvidenceStance, str]:
    """Return `(stance, method)` relative to the decomposition summary `scope`."""

    text = f"{title}\n{abstract or ''}"
    if decisions is None:
        return keyword_stance(text), "keywords"
    try:
        answers = await decisions.evaluate(
            record_state(scope, title, abstract), {STANCE_KEY: stance_question(mode)}
        )
    except Exception:
        return keyword_stance(text), "keywords"
    return stance_from_answer(answers.get(STANCE_KEY), text)


# --- Ranking helpers -----------------------------------------------------------------


def evidence_rank(level: EvidenceLevel | str | None) -> int:
    """1 = strongest. Unknown or missing levels rank after OTHER."""

    parsed = parse_level(level)
    return EVIDENCE_RANK[parsed] if parsed is not None else UNKNOWN_RANK


def is_opposing(stance: EvidenceStance | str | None) -> bool:
    return parse_stance(stance) in OPPOSING_STANCES


def is_contrarian(stance: EvidenceStance | str | None) -> bool:
    return parse_stance(stance) in CONTRARIAN_STANCES


_HIGH_START = frozenset(
    {EvidenceLevel.META_ANALYSIS, EvidenceLevel.SYSTEMATIC_REVIEW, EvidenceLevel.RCT}
)
_LOW_START = frozenset(
    {
        EvidenceLevel.NON_RANDOMIZED_TRIAL,
        EvidenceLevel.COHORT,
        EvidenceLevel.CASE_CONTROL,
        EvidenceLevel.CROSS_SECTIONAL,
        EvidenceLevel.GUIDELINE,
    }
)
GRADE_ORDER = (
    GradeCertainty.VERY_LOW,
    GradeCertainty.LOW,
    GradeCertainty.MODERATE,
    GradeCertainty.HIGH,
)


def grade_start(levels: Iterable[EvidenceLevel | str | None]) -> GradeCertainty:
    """GRADE start level from the strongest design: randomized evidence HIGH, observational
    LOW, everything else VERY_LOW."""

    parsed = {parse_level(level) for level in levels} - {None}
    if parsed & _HIGH_START:
        return GradeCertainty.HIGH
    if parsed & _LOW_START:
        return GradeCertainty.LOW
    return GradeCertainty.VERY_LOW


def cap_certainty(certainty: GradeCertainty, start: GradeCertainty) -> GradeCertainty:
    """GRADE never rises above the study-design start level."""

    return min(certainty, start, key=GRADE_ORDER.index)


def level_counts(levels: Iterable[EvidenceLevel | str | None]) -> Mapping[str, int]:
    counts: dict[str, int] = {}
    for level in levels:
        key = str(parse_level(level) or "UNKNOWN")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: evidence_rank(item[0])))
