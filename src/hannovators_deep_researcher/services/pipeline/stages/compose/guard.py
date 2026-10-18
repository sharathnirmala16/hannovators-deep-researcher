"""Deterministic UI component guard: mount only components that have data to show."""

from dataclasses import dataclass

from hannovators_deep_researcher.models.enums import DomainMode, UiComponentId


@dataclass(frozen=True, slots=True)
class AvailableData:
    domain: DomainMode
    has_sources: bool
    has_claims: bool
    has_synthesis: bool
    has_highlights: bool


def guard_components(data: AvailableData) -> list[UiComponentId]:
    """Scope builder and funnel always; every other component only when its data exists."""

    evidence = (
        UiComponentId.EVIDENCE_PROFILE_TABLE
        if data.domain is DomainMode.MEDICAL
        else UiComponentId.CLAIM_MATRIX
    )
    wanted = {
        UiComponentId.SCOPE_BUILDER: True,
        UiComponentId.SCREENING_FUNNEL: True,
        evidence: data.has_claims,
        UiComponentId.SYNTHESIS_PANEL: data.has_synthesis,
        UiComponentId.PDF_VIEWER: data.has_highlights,
        UiComponentId.CITATION_GRAPH: data.has_sources,
    }
    return [component for component in UiComponentId if wanted.get(component, False)]
