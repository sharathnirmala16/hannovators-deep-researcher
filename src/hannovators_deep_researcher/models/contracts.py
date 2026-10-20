"""Workspace contracts: decomposition, synthesis, views, WorkspaceState, and API bodies."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from hannovators_deep_researcher.models.base import ContractModel, NonEmptyText, Probability
from hannovators_deep_researcher.models.enums import (
    ClaimArm,
    ClaimKind,
    ClaimVerdict,
    Directness,
    DomainMode,
    EvidenceLevel,
    EvidenceStance,
    GradeCertainty,
    HighlightMethod,
    RecommendationDirection,
    RecommendationStrength,
    RejectionCode,
    RequestedDomainMode,
    RobJudgement,
    SearchIntent,
    SourceDecisionKind,
    SourceLinkKind,
    SourceOrigin,
    SourceStatus,
    StageId,
    UiComponentId,
    WorkspaceStatus,
)

DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
DEFAULT_EMBEDDING_DIMENSIONS = 1024
MIN_EMBEDDING_DIMENSIONS = 32
MAX_EMBEDDING_DIMENSIONS = 4096

Rect = tuple[float, float, float, float]


# --- Decomposition -----------------------------------------------------------------


class InterventionComparisonPair(ContractModel):
    intervention: str
    comparison: str


class PicotsDecomposition(ContractModel):
    mode: Literal[DomainMode.MEDICAL] = DomainMode.MEDICAL
    population: str
    interventions: list[str] = Field(default_factory=list)
    comparisons: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    timing: str | None = None
    study_designs: list[str] = Field(default_factory=list)
    ic_pairs: list[InterventionComparisonPair] = Field(default_factory=list)


class ScopeDecomposition(ContractModel):
    mode: Literal[DomainMode.GENERAL] = DomainMode.GENERAL
    entities: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    time_horizon: str | None = None
    counter_hypotheses: list[str] = Field(default_factory=list)


Decomposition = Annotated[PicotsDecomposition | ScopeDecomposition, Field(discriminator="mode")]
DECOMPOSITION_ADAPTER: TypeAdapter[PicotsDecomposition | ScopeDecomposition] = TypeAdapter(
    Decomposition
)


# --- Synthesis ---------------------------------------------------------------------


class GradeAssessment(ContractModel):
    """Per-outcome GRADE certainty with a short judgement for each downgrade domain."""

    certainty: GradeCertainty
    risk_of_bias: str
    inconsistency: str
    indirectness: str
    imprecision: str
    publication_bias: str


class PairwiseSummary(ContractModel):
    """One intervention-versus-comparison outcome (claim versus counter-claim in GENERAL)."""

    intervention: str
    comparison: str
    outcome: str
    summary: str
    source_ids: list[str] = Field(default_factory=list)
    grade: GradeAssessment


class Recommendation(ContractModel):
    direction: RecommendationDirection
    strength: RecommendationStrength
    text: str


class Provenance(ContractModel):
    canary: str
    models: dict[str, str] = Field(default_factory=dict)
    generated_at: datetime


class Synthesis(ContractModel):
    pairwise_summaries: list[PairwiseSummary] = Field(default_factory=list)
    analysis: str
    recommendation: Recommendation
    provenance: Provenance


# --- Workspace ---------------------------------------------------------------------


class WorkspaceSettings(ContractModel):
    """Per-workspace run settings. Embedding fields are copied from Settings at creation."""

    screen_votes_t: int = Field(default=2, ge=1, le=3)
    appraise_m: int = Field(default=2, ge=0)
    screen_top_n: int = Field(default=15, ge=1)
    appraise_top_k: int = Field(default=6, ge=1)
    search_max_rounds: int = Field(default=3, ge=1)
    search_hits_min: int = Field(default=1, ge=0)
    search_hits_max: int = Field(default=5000, ge=1)
    highlight_confidence_floor: Probability = 0.6
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_dimensions: int = Field(
        default=DEFAULT_EMBEDDING_DIMENSIONS,
        ge=MIN_EMBEDDING_DIMENSIONS,
        le=MAX_EMBEDDING_DIMENSIONS,
    )

    @model_validator(mode="after")
    def _check_hit_window(self) -> Self:
        if self.search_hits_min > self.search_hits_max:
            raise ValueError("search_hits_min must not exceed search_hits_max")
        return self


class WorkspaceView(ContractModel):
    id: str
    research_question: str
    domain_mode: RequestedDomainMode
    status: WorkspaceStatus
    current_stage: StageId | None = None
    auto_continue: bool
    settings: WorkspaceSettings
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class QueryView(ContractModel):
    """One row of `search_queries`. `tool` is `pubmed`, `web:<provider>`, or `elink`."""

    id: str
    workspace_id: str
    iteration: int = Field(ge=0)
    tool: str
    core_query: str
    applied_filters: str = ""
    raw_hit_count: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    refinement_note: str | None = None
    created_at: datetime


class Rob2Assessment(ContractModel):
    """RoB 2 judgement per domain name, plus the overall judgement."""

    domains: dict[str, RobJudgement] = Field(default_factory=dict)
    overall: RobJudgement


SOURCE_DECISION_REASON_CHARS = 1000


class SourceDecision(ContractModel):
    """The researcher's override of a source. `agent_status` is the status the pipeline gave
    it before any manual decision; `applied` is False until a re-synthesis has used it."""

    decision: SourceDecisionKind
    reason: str | None = None
    agent_status: SourceStatus
    decided_at: datetime
    applied: bool = False
    trajectory_step_id: int | None = None


class SourceView(ContractModel):
    """A source as the UI sees it. The abstract is not in the state payload."""

    id: str
    origin: SourceOrigin
    external_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    url: str | None = None
    study_design: str | None = None
    status: SourceStatus
    screen_score: float | None = None
    screen_z: float | None = None
    screen_votes: int | None = Field(default=None, ge=0)
    m_score: int | None = Field(default=None, ge=0)
    directness: Directness | None = None
    rob2: Rob2Assessment | None = None
    rejection_code: RejectionCode | None = None
    decision_explanation: str | None = None
    raw_url: str | None = None
    highlighted_url: str | None = None
    evidence_level: EvidenceLevel | None = None
    evidence_rank: int | None = Field(default=None, ge=1)
    stance: EvidenceStance | None = None
    search_intent: SearchIntent | None = None
    found_by: str | None = None
    decision: SourceDecision | None = None


class SourceDetail(ContractModel):
    """`GET /api/workspaces/{id}/sources/{source_id}`: one source with its full audit record."""

    source: SourceView
    abstract: str | None = None
    pdf_url: str | None = None
    screen: dict[str, object] = Field(default_factory=dict)
    appraisal: dict[str, object] = Field(default_factory=dict)
    extra: dict[str, object] = Field(default_factory=dict)
    chunk_count: int = Field(default=0, ge=0)
    claim_ids: list[str] = Field(default_factory=list)
    trajectory_step_ids: list[int] = Field(default_factory=list)


class WorkspaceSummary(ContractModel):
    """One row of `GET /api/workspaces` (newest first)."""

    id: str
    research_question: str
    domain_mode: RequestedDomainMode
    status: WorkspaceStatus
    current_stage: StageId | None = None
    created_at: datetime
    updated_at: datetime
    source_count: int = Field(default=0, ge=0)
    promoted_count: int = Field(default=0, ge=0)
    seed_count: int = Field(default=0, ge=0)


class Funnel(ContractModel):
    seeds: int = Field(default=0, ge=0)
    raw: int = Field(default=0, ge=0)
    screen_promoted: int = Field(default=0, ge=0)
    screen_discounted: int = Field(default=0, ge=0)
    appraise_promoted: int = Field(default=0, ge=0)
    appraise_discounted: int = Field(default=0, ge=0)
    acquire_failed: int = Field(default=0, ge=0)


class ClaimView(ContractModel):
    id: str
    source_id: str | None = None
    kind: ClaimKind
    label: str
    text: str
    quote: str | None = None
    verdict: ClaimVerdict
    confidence: Probability | None = None
    outcome: str | None = None
    arm: ClaimArm | None = None
    highlight_ids: list[str] = Field(default_factory=list)


class HighlightView(ContractModel):
    """Highlight rectangles `[x0, y0, x1, y1]` in PDF points on a 1-based page."""

    id: str
    source_id: str
    claim_id: str
    page: int = Field(ge=1)
    rects: list[Rect] = Field(default_factory=list)
    method: HighlightMethod
    score: float | None = None
    color: str
    pdf_url: str | None = None


class GraphNode(ContractModel):
    id: str
    label: str
    status: SourceStatus
    origin: SourceOrigin


class GraphEdge(ContractModel):
    source: str
    target: str
    kind: SourceLinkKind


class GraphView(ContractModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class WorkspaceState(ContractModel):
    """The whole workspace view returned by `GET /api/workspaces/{id}`."""

    workspace: WorkspaceView
    decomposition: Decomposition | None = None
    queries: list[QueryView] = Field(default_factory=list)
    sources: list[SourceView] = Field(default_factory=list)
    funnel: Funnel = Field(default_factory=Funnel)
    claims: list[ClaimView] = Field(default_factory=list)
    highlights: list[HighlightView] = Field(default_factory=list)
    synthesis: Synthesis | None = None
    ui_components: list[UiComponentId] = Field(default_factory=list)
    last_event_id: int | None = None


# --- HTTP API bodies ---------------------------------------------------------------


class CreateWorkspaceRequest(ContractModel):
    """Body of `POST /api/workspaces`. The server sets the embedding settings itself."""

    research_question: NonEmptyText
    domain_mode: RequestedDomainMode = RequestedDomainMode.AUTO
    auto_continue: bool = False
    settings: WorkspaceSettings | None = None


class SeedReferenceRequest(ContractModel):
    """JSON body of `POST /api/workspaces/{id}/seeds`: exactly one of pmid, doi, or url."""

    pmid: NonEmptyText | None = None
    doi: NonEmptyText | None = None
    url: NonEmptyText | None = None

    @model_validator(mode="after")
    def _check_exactly_one(self) -> Self:
        given = [value for value in (self.pmid, self.doi, self.url) if value is not None]
        if len(given) != 1:
            raise ValueError("give exactly one of pmid, doi, or url")
        return self


class SourceDecisionRequest(ContractModel):
    """Body of `POST /api/workspaces/{id}/sources/{source_id}/decision`."""

    decision: SourceDecisionKind
    reason: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, max_length=SOURCE_DECISION_REASON_CHARS),
        ]
        | None
    ) = None


class ApiErrorDetail(ContractModel):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$")]
    message: str


class ApiError(ContractModel):
    """Error body: `{"detail": {"code": "<UPPER_SNAKE>", "message": "<text>"}}`."""

    detail: ApiErrorDetail
