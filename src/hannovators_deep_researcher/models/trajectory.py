"""Trajectory contracts: the auditable, network-tab style record of every agent and user action.

Every port call (LLM, Jev, search, fetch, download, embed), every keep/remove verdict, every
stage, every chat turn, and every user action becomes one `TrajectoryStep`. The list endpoint
returns `TrajectoryStepSummary` rows; the detail endpoint adds the request and response bodies.
"""

from datetime import datetime

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel, NonEmptyText, Probability
from hannovators_deep_researcher.models.enums import (
    StageId,
    TrajectoryActor,
    TrajectoryKind,
    TrajectoryStatus,
    VerdictOutcome,
)


class TrajectoryStepSummary(ContractModel):
    """One row in the trajectory table. `id` is monotonic, so it doubles as a cursor."""

    id: int = Field(ge=1)
    workspace_id: str
    parent_id: int | None = None
    actor: TrajectoryActor
    kind: TrajectoryKind
    stage: StageId | None = None
    name: str
    """Short operation label, e.g. `tavily.search`, `pubmed.esearch`, `nemotron.APPRAISE`,
    `jev.screen`, `screen.verdict`, `user.decomposition.edit`."""
    target: str | None = None
    """URL, model ID, or endpoint the step talked to."""
    status: TrajectoryStatus
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    summary: str = ""
    source_ids: list[str] = Field(default_factory=list)
    outcome: VerdictOutcome | None = None
    confidence: Probability | None = None
    error: str | None = None


class TrajectoryStep(TrajectoryStepSummary):
    """A step with its request and response bodies (prompts, queries, results, probabilities)."""

    request: dict[str, object] = Field(default_factory=dict)
    response: dict[str, object] = Field(default_factory=dict)


class TrajectoryPage(ContractModel):
    """`GET /api/workspaces/{id}/trajectory`. `next_after` is the cursor for the next page."""

    steps: list[TrajectoryStepSummary] = Field(default_factory=list)
    next_after: int | None = None
    total: int = Field(default=0, ge=0)


class UserActionRequest(ContractModel):
    """`POST /api/workspaces/{id}/trajectory/actions`: a UI action the server cannot see itself
    (for example opening a source, following a citation, or switching a filter)."""

    name: NonEmptyText
    summary: str = ""
    target: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    details: dict[str, object] = Field(default_factory=dict)
