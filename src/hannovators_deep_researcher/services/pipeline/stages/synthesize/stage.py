"""Synthesize APPRAISE_PROMOTED sources into a Synthesis with GRADE and a recommendation.

Sources are labelled S1, S2, ... strongest design first. GRADE certainty per pair is capped at
the study-design start level (randomized evidence HIGH, observational LOW). The analysis always
names the strongest opposing or null evidence and the alternatives, with their source IDs.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from secrets import token_hex

from hannovators_deep_researcher.configuration.settings import ProviderMode
from hannovators_deep_researcher.models.contracts import (
    GradeAssessment,
    PairwiseSummary,
    PicotsDecomposition,
    Provenance,
    Recommendation,
    ScopeDecomposition,
    Synthesis,
)
from hannovators_deep_researcher.models.enums import (
    ClaimKind,
    ClaimVerdict,
    EvidenceStance,
    GradeCertainty,
    ModelRole,
    RecommendationDirection,
    RecommendationStrength,
    SourceStatus,
    TraceEventKind,
    TrajectoryKind,
)
from hannovators_deep_researcher.persistence.tables import ClaimRow, SourceRow
from hannovators_deep_researcher.services.evidence import (
    GRADE_ORDER,
    cap_certainty,
    evidence_rank,
    grade_start,
    is_opposing,
    parse_stance,
)
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.synthesize.schema import (
    SYSTEM,
    SynthesisDraft,
)
from hannovators_deep_researcher.services.workspace_state import parse_decomposition

_ABSTRACT_CHARS = 2_500
INSUFFICIENT_EVIDENCE = "Insufficient evidence"
_LABEL = re.compile(r"\bS(\d+)\b")
_LABEL_ANY = re.compile(r"\b[Ss]\d+\b")
Decomposition = PicotsDecomposition | ScopeDecomposition
SYNTHESIS_ATTEMPTS = 2
FALLBACK_NOTE = "Not assessed (automatic summary; the synthesis model gave no usable answer)."


@dataclass(frozen=True, slots=True)
class Evidence:
    """The labelled sources the model saw, strongest design first."""

    labels: dict[str, str]
    sources: dict[str, SourceRow]
    excluded_opposing: SourceRow | None = None
    """The strongest opposing or null source that appraisal excluded (it passed screening)."""

    def ids(self, labels: list[str]) -> list[str]:
        """Source IDs for labels; tolerates "[S1]", "S1, S3", or "s2" from the model."""

        found = (match.upper() for label in labels for match in _LABEL_ANY.findall(label))
        return list(dict.fromkeys(self.labels[label] for label in found if label in self.labels))

    def cite(self, text: str) -> str:
        """Replace S-labels in prose with `[<source id>]`, so citations are auditable."""

        def swap(match: re.Match[str]) -> str:
            source_id = self.labels.get(match[0])
            return f"[{source_id}]" if source_id else match[0]

        return _LABEL.sub(swap, text)

    def with_stance(self, *stances: EvidenceStance) -> list[SourceRow]:
        return [
            source for source in self.sources.values() if parse_stance(source.stance) in stances
        ]


def _provenance(ctx: StageContext) -> Provenance:
    settings = ctx.app_settings
    if settings.provider_mode == ProviderMode.FAKE:
        models = {"agent": "fake", "decisions": "fake", "embeddings": "fake"}
    else:
        models = {
            "appraise": settings.model_for(ModelRole.APPRAISE),
            "synthesize": settings.model_for(ModelRole.SYNTHESIZE),
            "decisions": settings.jev_model,
            "embeddings": settings.embedding_model,
        }
    return Provenance(
        canary=f"hdr-{ctx.workspace_id[:8]}-{token_hex(6)}",
        models=models,
        generated_at=datetime.now(UTC),
    )


def insufficient_evidence(provenance: Provenance) -> Synthesis:
    return Synthesis(
        analysis=f"{INSUFFICIENT_EVIDENCE}: no source passed appraisal.",
        recommendation=Recommendation(
            direction=RecommendationDirection.NONE,
            strength=RecommendationStrength.CONDITIONAL,
            text=f"{INSUFFICIENT_EVIDENCE} to make a recommendation.",
        ),
        provenance=provenance,
    )


def _source_block(label: str, source: SourceRow, claims: list[ClaimRow]) -> str:
    rob = json.loads(source.rob2_json)["overall"] if source.rob2_json else "n/a"
    lines = [
        f"[{label}] {source.title} ({source.year or 'n.d.'})",
        f"evidence level: {source.evidence_level or 'unknown'}; GRADE start: "
        f"{grade_start([source.evidence_level])}; stance: {source.stance or 'UNCLEAR'}; "
        f"found by: {source.search_intent or 'n/a'} search",
        f"design: {source.study_design or 'unknown'}; M: {source.m_score}; "
        f"directness: {source.directness or 'n/a'}; RoB 2 overall: {rob}",
        f"abstract: {(source.abstract or '')[:_ABSTRACT_CHARS]}",
    ]
    lines += [f"- {claim.kind} {claim.label}: {claim.text} [{claim.verdict}]" for claim in claims]
    return "\n".join(lines)


def _contrarian_note(evidence: Evidence) -> str:
    opposing = evidence.with_stance(
        EvidenceStance.OPPOSES, EvidenceStance.NULL_RESULT, EvidenceStance.MIXED
    )
    alternatives = evidence.with_stance(EvidenceStance.ALTERNATIVE)
    by_id = {source_id: label for label, source_id in evidence.labels.items()}

    def names(sources: list[SourceRow]) -> str:
        return ", ".join(f"{by_id[s.id]} ({s.stance}, {s.evidence_level})" for s in sources)

    return (
        f"Opposing, null, or mixed evidence to discuss: {names(opposing) or 'none found'}\n"
        f"Alternative-intervention evidence to discuss: {names(alternatives) or 'none found'}"
    )


def _strongest_opposing(evidence: Evidence) -> SourceRow | None:
    opposing = [source for source in evidence.sources.values() if is_opposing(source.stance)]
    if not opposing:
        opposing = evidence.with_stance(EvidenceStance.MIXED)
    return min(opposing, key=lambda source: evidence_rank(source.evidence_level), default=None)


def _pairs(draft: SynthesisDraft, evidence: Evidence) -> list[PairwiseSummary]:
    all_levels = [source.evidence_level for source in evidence.sources.values()]
    pairs = []
    for pair in draft.pairwise_summaries:
        source_ids = evidence.ids(pair.source_labels)
        levels = [evidence.sources[item].evidence_level for item in source_ids] or all_levels
        start = grade_start(levels)
        grade = pair.grade.to_contract()
        if cap_certainty(grade.certainty, start) != grade.certainty:
            grade = grade.model_copy(
                update={
                    "certainty": cap_certainty(grade.certainty, start),
                    "risk_of_bias": f"{grade.risk_of_bias} (capped at the {start} start level "
                    "for these study designs)",
                }
            )
        pairs.append(
            PairwiseSummary(
                intervention=pair.intervention,
                comparison=pair.comparison,
                outcome=pair.outcome,
                summary=evidence.cite(pair.summary),
                source_ids=source_ids,
                grade=grade,
            )
        )
    return pairs


def _opposing_section(draft: SynthesisDraft, evidence: Evidence) -> str:
    return opposing_section(draft.opposing_evidence, draft.opposing_source_labels, evidence)


def opposing_section(prose: str, labels: list[str], evidence: Evidence) -> str:
    """The model's opposing-evidence prose, always citing the strongest opposing or null
    source (by evidence level) when the promoted evidence has one."""

    cited = evidence.ids(labels)
    text = evidence.cite(prose.strip())
    strongest = _strongest_opposing(evidence)
    if strongest is not None and strongest.id not in cited:
        text += (
            f' Strongest opposing or null evidence: "{strongest.title}" '
            f"({strongest.evidence_level or 'unknown design'}, {strongest.stance}) "
            f"[{strongest.id}]."
        )
        cited.append(strongest.id)
    outside = evidence.excluded_opposing
    if strongest is None and outside is not None:
        reason = (outside.decision_explanation or "excluded at appraisal")[:160]
        text += (
            f" No included study opposes; the strongest opposing or null record outside the "
            f'included studies is "{outside.title}" ({outside.evidence_level or "unknown design"}, '
            f"{outside.stance}; {reason}) [{outside.id}]."
        )
        cited.append(outside.id)
    if not text.strip():
        text = "Targeted searches for null, negative, and harm evidence found no opposing source."
    suffix = f" (sources: {', '.join(cited)})" if cited else ""
    return f"Opposing and null evidence: {text.strip()}{suffix}"


def _alternatives_section(draft: SynthesisDraft, evidence: Evidence) -> str:
    return alternatives_section(draft.alternatives, draft.alternative_source_labels, evidence)


def alternatives_section(prose: str, labels: list[str], evidence: Evidence) -> str:
    cited = evidence.ids(labels)
    cited += [
        source.id
        for source in evidence.with_stance(EvidenceStance.ALTERNATIVE)
        if source.id not in cited
    ]
    text = evidence.cite(prose.strip()) or "No alternative-intervention source was promoted."
    suffix = f" (sources: {', '.join(cited)})" if cited else ""
    return f"Alternatives: {text}{suffix}"


def to_synthesis(draft: SynthesisDraft, evidence: Evidence, provenance: Provenance) -> Synthesis:
    """Map source labels to IDs, cap GRADE at the design start level, and add the opposing-
    evidence and alternatives sections to the analysis."""

    sections = [
        evidence.cite(draft.analysis),
        _opposing_section(draft, evidence),
        _alternatives_section(draft, evidence),
    ]
    if draft.cost_and_preference_considerations:
        notes = "\n".join(f"- {note}" for note in draft.cost_and_preference_considerations)
        sections.append(f"Cost and preference considerations (not evidence):\n{notes}")
    return Synthesis(
        pairwise_summaries=_pairs(draft, evidence),
        analysis="\n\n".join(sections),
        recommendation=draft.recommendation.to_contract().model_copy(
            update={"text": evidence.cite(draft.recommendation.text)}
        ),
        provenance=provenance,
    )


async def build_synthesis(ctx: StageContext) -> Synthesis:
    provenance = _provenance(ctx)
    sources = await ctx.repositories.list_sources(
        ctx.workspace_id, [SourceStatus.APPRAISE_PROMOTED]
    )
    if not sources:
        await ctx.emit(TraceEventKind.WARNING, "no promoted sources; insufficient evidence")
        return insufficient_evidence(provenance)
    sources = sorted(sources, key=lambda source: evidence_rank(source.evidence_level))
    workspace = await ctx.repositories.get_workspace(ctx.workspace_id)
    claims = await ctx.repositories.list_claims(ctx.workspace_id)
    labels = {f"S{index}": source.id for index, source in enumerate(sources, start=1)}
    excluded = await ctx.repositories.list_sources(
        ctx.workspace_id, [SourceStatus.APPRAISE_DISCOUNTED]
    )
    opposing = [source for source in excluded if is_opposing(source.stance)]
    evidence = Evidence(
        labels,
        {source.id: source for source in sources},
        min(opposing, key=lambda source: evidence_rank(source.evidence_level), default=None),
    )
    blocks = [
        _source_block(label, source, [claim for claim in claims if claim.source_id == source.id])
        for label, source in zip(labels, sources, strict=True)
    ]
    user = (
        f"Research question: {workspace.research_question if workspace else ''}\n\n"
        f"Decomposition:\n{workspace.decomposition_json if workspace else ''}\n\n"
        f"{_contrarian_note(evidence)}\n\n"
        "Evidence (strongest design first):\n\n" + "\n\n".join(blocks)
    )
    decomposition = parse_decomposition(workspace) if workspace else None
    promoted_claims = [claim for claim in claims if claim.source_id in evidence.sources]
    draft = await _draft(ctx, user)
    if draft is None:
        # PLAN.md section 3: stages 3 to 7 tolerate provider failure. The evidence profile
        # still gets one row per outcome, built from the appraised metrics.
        return fallback_synthesis(evidence, promoted_claims, decomposition, provenance)
    synthesis = to_synthesis(draft, evidence, provenance)
    if not synthesis.pairwise_summaries:
        pairs = fallback_pairs(evidence, promoted_claims, decomposition)
        synthesis = synthesis.model_copy(update={"pairwise_summaries": pairs})
    return synthesis


async def _draft(ctx: StageContext, user: str) -> SynthesisDraft | None:
    """The model's draft; a second attempt on failure (sampling at temperature 1.0 varies)."""

    for attempt in range(1, SYNTHESIS_ATTEMPTS + 1):
        try:
            return await ctx.chat.complete_json(
                role=ModelRole.SYNTHESIZE, system=SYSTEM, user=user, schema=SynthesisDraft
            )
        except Exception as error:
            final = attempt == SYNTHESIS_ATTEMPTS
            await ctx.emit(
                TraceEventKind.WARNING,
                f"Synthesis model failed ({type(error).__name__}, attempt {attempt}); "
                + ("built an automatic summary" if final else "retrying"),
                {"error": str(error)[:300], "attempt": attempt},
            )
    return None


def _arms(decomposition: Decomposition | None) -> tuple[str, str]:
    if isinstance(decomposition, PicotsDecomposition):
        return (
            "; ".join(decomposition.interventions) or "Intervention",
            "; ".join(decomposition.comparisons) or "Comparison",
        )
    if decomposition is not None:
        claim = decomposition.claims[0] if decomposition.claims else "Scope claims"
        counter = (
            decomposition.counter_hypotheses[0]
            if decomposition.counter_hypotheses
            else "Counter-claims"
        )
        return claim, counter
    return "Intervention", "Comparison"


def _default_outcome(decomposition: Decomposition | None) -> str:
    if isinstance(decomposition, PicotsDecomposition) and decomposition.outcomes:
        return decomposition.outcomes[0]
    if decomposition is not None and not isinstance(decomposition, PicotsDecomposition):
        return decomposition.metrics[0] if decomposition.metrics else "Main claims"
    return "Main outcome"


def fallback_pairs(
    evidence: Evidence, claims: list[ClaimRow], decomposition: Decomposition | None
) -> list[PairwiseSummary]:
    """One pairwise row per reported outcome (from METRIC/CLAIM payloads), else one row for the
    first review outcome over all promoted sources. GRADE starts at the design level and is
    rated one step lower, because no model judged the five domains."""

    intervention, comparison = _arms(decomposition)
    by_outcome: dict[str, list[ClaimRow]] = {}
    for claim in claims:
        if claim.kind == ClaimKind.RECOMMENDATION:
            continue
        outcome = _claim_outcome(claim) or _default_outcome(decomposition)
        by_outcome.setdefault(outcome, []).append(claim)
    if not by_outcome:
        by_outcome[_default_outcome(decomposition)] = []
    pairs = []
    for outcome, group in by_outcome.items():
        source_ids = list(dict.fromkeys(c.source_id for c in group if c.source_id)) or list(
            evidence.sources
        )
        start = grade_start([evidence.sources[item].evidence_level for item in source_ids])
        lower = GRADE_ORDER[max(GRADE_ORDER.index(start) - 1, 0)]
        facts = "; ".join(f"{claim.text} [{claim.source_id}]" for claim in group[:6])
        pairs.append(
            PairwiseSummary(
                intervention=intervention,
                comparison=comparison,
                outcome=outcome,
                summary=facts or f"{len(source_ids)} appraised source(s); no metric reported.",
                source_ids=source_ids,
                grade=GradeAssessment(
                    certainty=lower,
                    risk_of_bias=FALLBACK_NOTE,
                    inconsistency=FALLBACK_NOTE,
                    indirectness=FALLBACK_NOTE,
                    imprecision=FALLBACK_NOTE,
                    publication_bias=FALLBACK_NOTE,
                ),
            )
        )
    return pairs


def _claim_outcome(claim: ClaimRow) -> str | None:
    try:
        payload = json.loads(claim.payload_json) if claim.payload_json else {}
    except ValueError:
        return None
    outcome = payload.get("outcome") if isinstance(payload, dict) else None
    return outcome.strip() if isinstance(outcome, str) and outcome.strip() else None


def fallback_synthesis(
    evidence: Evidence,
    claims: list[ClaimRow],
    decomposition: Decomposition | None,
    provenance: Provenance,
) -> Synthesis:
    """A model-free synthesis: evidence rows per outcome, the strongest opposing or null
    source, and no recommendation."""

    listed = "; ".join(
        f"{source.title[:120]} ({source.evidence_level or 'unknown design'}, "
        f"{source.stance or 'UNCLEAR'}) [{source.id}]"
        for source in evidence.sources.values()
    )
    sections = [
        "Automatic summary: the synthesis model gave no usable answer, so the appraised "
        f"evidence is listed strongest design first: {listed}.",
        opposing_section("", [], evidence),
        alternatives_section("", [], evidence),
    ]
    return Synthesis(
        pairwise_summaries=fallback_pairs(evidence, claims, decomposition),
        analysis="\n\n".join(sections),
        recommendation=Recommendation(
            direction=RecommendationDirection.NONE,
            strength=RecommendationStrength.CONDITIONAL,
            text="No recommendation: the synthesis model failed; review the evidence rows.",
        ),
        provenance=provenance,
    )


def _cited(synthesis: Synthesis) -> list[str]:
    ids = [source_id for pair in synthesis.pairwise_summaries for source_id in pair.source_ids]
    ids += re.findall(r"\[([0-9a-f-]{36})\]", synthesis.analysis)
    return list(dict.fromkeys(ids))


async def run(ctx: StageContext) -> None:
    synthesis = await build_synthesis(ctx)
    await ctx.repositories.update_workspace_fields(
        ctx.workspace_id, synthesis_json=synthesis.model_dump_json()
    )
    recommendation = synthesis.recommendation
    await ctx.repositories.create_claim(
        ctx.workspace_id,
        kind=ClaimKind.RECOMMENDATION,
        label="Recommendation",
        text=recommendation.text,
        verdict=ClaimVerdict.UNVERIFIED
        if recommendation.direction == RecommendationDirection.NONE
        else ClaimVerdict.SUPPORTED,
        payload_json=json.dumps(
            {"direction": recommendation.direction, "strength": recommendation.strength}
        ),
    )
    certainties = [pair.grade.certainty for pair in synthesis.pairwise_summaries]
    await ctx.trajectory.record(
        kind=TrajectoryKind.VERDICT,
        name="synthesize.verdict",
        summary=f"Recommendation {recommendation.direction} ({recommendation.strength}): "
        f"{recommendation.text}"[:400],
        response={
            "direction": recommendation.direction,
            "strength": recommendation.strength,
            "recommendation": recommendation.text,
            "pairs": [
                {
                    "intervention": pair.intervention,
                    "comparison": pair.comparison,
                    "outcome": pair.outcome,
                    "certainty": pair.grade.certainty,
                    "source_ids": pair.source_ids,
                }
                for pair in synthesis.pairwise_summaries
            ],
            "analysis": synthesis.analysis,
            "canary": synthesis.provenance.canary,
        },
        source_ids=_cited(synthesis),
        confidence=_certainty_confidence(certainties),
    )
    await ctx.emit(
        TraceEventKind.DECISION,
        f"synthesis: {recommendation.direction} ({recommendation.strength})",
        {"pairs": len(synthesis.pairwise_summaries), "canary": synthesis.provenance.canary},
    )


_CERTAINTY_SCORE = {
    GradeCertainty.HIGH: 0.9,
    GradeCertainty.MODERATE: 0.7,
    GradeCertainty.LOW: 0.45,
    GradeCertainty.VERY_LOW: 0.2,
}


def _certainty_confidence(certainties: list[GradeCertainty]) -> float | None:
    """The best GRADE certainty as a rough confidence for the trajectory row."""

    return max((_CERTAINTY_SCORE[item] for item in certainties), default=None)
