"""Researcher decisions on sources: a manual include or exclude that overrides the agent.

An include sets APPRAISE_PROMOTED and an exclude sets APPRAISE_DISCOUNTED, so every view that
reads statuses (funnel, graph, synthesis inputs) follows the researcher. The agent's original
status, explanation, and screening/appraisal records stay on the source. Each decision records a
USER_ACTION trajectory step and stays `applied=False` until a re-synthesis uses it.
"""

from hannovators_deep_researcher.models.contracts import SourceDecision, SourceDecisionRequest
from hannovators_deep_researcher.models.enums import (
    SourceDecisionKind,
    SourceStatus,
    StageId,
    VerdictOutcome,
    WorkspaceStatus,
)
from hannovators_deep_researcher.persistence.queries.decisions import decided_sources
from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import SourceRow, utc_now
from hannovators_deep_researcher.services.trajectory import TrajectoryRecorder
from hannovators_deep_researcher.services.trajectory_wrappers import record_user_action
from hannovators_deep_researcher.services.workspace_state import (
    WorkspaceNotFoundError,
    parse_source_decision,
)

DECIDED_STATUS: dict[SourceDecisionKind, SourceStatus] = {
    SourceDecisionKind.INCLUDE: SourceStatus.APPRAISE_PROMOTED,
    SourceDecisionKind.EXCLUDE: SourceStatus.APPRAISE_DISCOUNTED,
}
_VERB = {SourceDecisionKind.INCLUDE: "Included", SourceDecisionKind.EXCLUDE: "Excluded"}
_OUTCOME = {
    SourceDecisionKind.INCLUDE: VerdictOutcome.KEPT,
    SourceDecisionKind.EXCLUDE: VerdictOutcome.REMOVED,
}
_TITLE_CHARS = 90


class SourceDecisionError(Exception):
    """A decision the API refuses; `status` is the HTTP status for the router."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


async def _decidable_source(
    repositories: Repositories, workspace_id: str, source_id: str, decision: SourceDecisionKind
) -> SourceRow:
    workspace = await repositories.get_workspace(workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)
    if workspace.status != WorkspaceStatus.COMPLETED:
        raise SourceDecisionError(
            409,
            "WORKSPACE_NOT_COMPLETED",
            f"Sources can be included or excluded once the run is completed "
            f"(the workspace is {workspace.status}).",
        )
    source = await repositories.get_source(source_id)
    if source is None or source.workspace_id != workspace_id:
        raise SourceDecisionError(
            404, "SOURCE_NOT_FOUND", f"source {source_id} not found in workspace {workspace_id}"
        )
    if source.status == SourceStatus.SEED:
        raise SourceDecisionError(
            422, "SEED_NOT_DECIDABLE", "Seeds are always read in full; they cannot be excluded."
        )
    if source.status == DECIDED_STATUS[decision]:
        raise SourceDecisionError(
            409,
            "DECISION_UNCHANGED",
            f"The source is already {DECIDED_STATUS[decision]}.",
        )
    return source


async def decide_source(
    repositories: Repositories,
    trajectory: TrajectoryRecorder,
    *,
    workspace_id: str,
    source_id: str,
    body: SourceDecisionRequest,
) -> SourceRow:
    """Apply a researcher decision and record it. Raises `SourceDecisionError` or
    `WorkspaceNotFoundError`."""

    source = await _decidable_source(repositories, workspace_id, source_id, body.decision)
    previous = parse_source_decision(source.decision_json)
    agent_status = previous.agent_status if previous else SourceStatus(source.status)
    new_status = DECIDED_STATUS[body.decision]
    reason = body.reason or None
    verb = _VERB[body.decision]
    step_id = await record_user_action(
        trajectory,
        workspace_id,
        f"user.source.{body.decision.lower()}",
        summary=f"{verb} {source.title[:_TITLE_CHARS]}" + (f": {reason}" if reason else ""),
        target=source.url or source.external_id,
        request={
            "decision": body.decision,
            "reason": reason,
            "title": source.title,
            "from_status": source.status,
            "to_status": new_status,
            "agent_status": agent_status,
            "agent_explanation": source.decision_explanation,
        },
        source_ids=[source.id],
        stage=StageId.APPRAISE,
        outcome=_OUTCOME[body.decision],
    )
    decision = SourceDecision(
        decision=body.decision,
        reason=reason,
        agent_status=agent_status,
        decided_at=utc_now(),
        trajectory_step_id=step_id,
    )
    return await repositories.update_source_fields(
        source.id, status=new_status, decision_json=decision.model_dump_json()
    )


async def pending_decisions(
    repositories: Repositories, workspace_id: str
) -> list[tuple[SourceRow, SourceDecision]]:
    """Decisions that no re-synthesis has used yet, oldest first."""

    pending = []
    for source in await decided_sources(repositories, workspace_id):
        decision = parse_source_decision(source.decision_json)
        if decision is not None and not decision.applied:
            pending.append((source, decision))
    return pending


async def pending_includes(repositories: Repositories, workspace_id: str) -> list[SourceRow]:
    """Sources the researcher included that are still included and not yet synthesized."""

    return [
        source
        for source, decision in await pending_decisions(repositories, workspace_id)
        if decision.decision == SourceDecisionKind.INCLUDE
        and source.status == SourceStatus.APPRAISE_PROMOTED
    ]


async def mark_decisions_applied(repositories: Repositories, workspace_id: str) -> int:
    """Mark every pending decision as used by the synthesis; return how many."""

    pending = await pending_decisions(repositories, workspace_id)
    for source, decision in pending:
        applied = decision.model_copy(update={"applied": True})
        await repositories.update_source_fields(source.id, decision_json=applied.model_dump_json())
    return len(pending)
