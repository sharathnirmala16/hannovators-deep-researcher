---
id: TASK-000052
title: Manual include/exclude of sources with re-synthesis
status: Done
assignee:
  - '@devin'
created_date: '2026-10-20 20:38'
updated_date: '2026-10-20 21:15'
labels:
  - backend
  - frontend
dependencies: []
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Researchers need to override the agent's screening and appraisal decisions: include a source the agent dropped, or exclude one it kept, with an optional reason. Each decision must be explicit in the trajectory so the audit trail shows the researcher changed the evidence base. Because an included source may never have been acquired or appraised, a re-synthesis action brings the decisions into the synthesis.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A researcher can include or exclude any non-seed source of a completed workspace from the Details pane and from a Sources table row, with an optional reason
- [x] #2 Each decision records a USER_ACTION trajectory step with the decision, the reason, and the before and after status
- [x] #3 The source shows an 'Included by you' or 'Excluded by you' tag with the reason and time; the agent's original decision stays visible
- [x] #4 The workspace shows how many decisions are not yet in the synthesis and offers Re-synthesize
- [x] #5 Re-synthesize acquires and appraises newly included sources without letting appraisal undo the decision, then re-runs synthesize, highlight, and compose
- [x] #6 Claims and highlights of excluded sources no longer appear in the evidence views
- [x] #7 All backend and frontend checks pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Backend: sources.decision_json column (Alembic 0004); SourceDecision contract on SourceView; POST /workspaces/{id}/sources/{source_id}/decision (COMPLETED only, not seeds) returning WorkspaceState; POST /workspaces/{id}/resynthesize (COMPLETED -> RUNNING) running a revision: acquire+appraise pending includes (forced promoted), synthesize (old recommendation claim removed), highlight new includes, compose; mark decisions applied. build_state hides claims/highlights of non-included sources.
Frontend: schema/enums/client methods; context actions decideSource and resynthesize; new feature source-decision (decision dialog, controls, decision note, resynthesis banner) composed at app level into source-details, source-table rows, and the evidence pane.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified in the browser against a backup copy of the local DB with PROVIDER_MODE=fake (separate backend on a temporary port): included an agent-excluded RCT from Details and excluded an included study from its Sources row, each with a reason; funnel, row tags, decision record, and pending bar updated; Re-synthesize ran acquire/appraise (included source appraised, kept included), synthesize (one recommendation claim), highlight, compose; decisions marked applied. Trajectory shows user.source.include (KEPT) and user.source.exclude (REMOVED) with reasons, plus user.run.resynthesize. Checks: ruff format/check, mypy, uv build, pytest (60 passed), pnpm check/build/test. New live e2e test tests/e2e/test_live_source_decisions.py collects; not run live (full pipeline spend).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Researchers can include or exclude any non-seed source of a completed run from the Details pane or a Sources row, with an optional reason. Each decision is a USER_ACTION trajectory step (outcome KEPT/REMOVED, reason, before/after status) and is stored on the source (migration 0004). A Re-synthesize action acquires and appraises newly included sources without undoing the decision, then re-runs synthesize, highlight, and compose. Excluded sources' claims and highlights leave the evidence views. Verified end to end in the browser on a DB copy with fake providers; all checks pass.
<!-- SECTION:FINAL_SUMMARY:END -->
