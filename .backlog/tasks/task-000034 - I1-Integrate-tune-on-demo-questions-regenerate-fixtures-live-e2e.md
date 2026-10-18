---
id: TASK-000034
title: 'I1 Integrate: tune on demo questions, regenerate fixtures, live e2e'
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
labels:
  - phase-3
  - backend
  - frontend
  - 'lane:i1'
milestone: m-3
dependencies:
  - TASK-000033
documentation:
  - PLAN.md
priority: high
type: task
ordinal: 34000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cross-lane issues only show up in real runs. This task tunes thresholds and prompts on the two demo questions and makes the live path the default.

Spec: PLAN.md card "I1 integrate" in section 7.6.
Runs on: main (single agent; contract fixes allowed here).
Depends on: Gate G2. Blocks: I2, I3, I4.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Two demo questions (one MEDICAL, one GENERAL) produce credible funnels, appraisals, and highlights
- [ ] #2 Frontend fixtures are regenerated from real runs and still pass both contract checks
- [ ] #3 The frontend uses the live API by default
- [ ] #4 tests/e2e contains the live e2e test
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 AGENTS.md checks pass on main after merge
- [ ] #2 PLAN.md updated in the same commit if a contract changed
<!-- DOD:END -->
