---
id: TASK-000036
title: I3 Playwright smoke test and docs
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
labels:
  - phase-3
  - frontend
  - 'lane:i3'
milestone: m-3
dependencies:
  - TASK-000034
documentation:
  - PLAN.md
priority: medium
type: task
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
One browser test protects the demo path; README and AGENTS.md must match the final commands.

Spec: PLAN.md card "I3 smoke + docs" in section 7.6 and section 8.
Depends on: I1. Parallel with: I2, I4.
Worktree: lane/i3-smoke
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 @playwright/test is installed and one smoke test runs in fixture mode: new run -> funnel -> metric cell -> PDF viewer at the page
- [ ] #2 vitest.config.ts excludes tests/** so Vitest ignores the Playwright spec
- [ ] #3 README and AGENTS.md list the final run and test commands
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; `pnpm check` and `pnpm build` pass; `pnpm test` passes when tests exist
- [ ] #3 Feature renders both fixtures (medical and general) without console errors
<!-- DOD:END -->
