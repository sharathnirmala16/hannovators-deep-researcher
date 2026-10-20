---
id: TASK-000050
title: 'R2 UI redesign: annotated paper visual system'
status: Done
assignee: []
created_date: '2026-10-20 17:39'
updated_date: '2026-10-20 17:39'
labels:
  - frontend
  - design
  - round-2
dependencies: []
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The UI looked like unstyled HTML; two lanes built the shell and the trajectory view separately with different styling, and a monochrome workaround made states hard to tell apart because the IDE preview browser renders translucent colors wrongly.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 One token system (PLAN.md 10.3) with solid colors only is used by the shell, all panes, and the trajectory view
- [x] #2 Status, stance, GRADE certainty, and RoB 2 have distinct semantic colors
- [x] #3 Research questions render TeX as readable text
- [x] #4 Each pane has one scroll area and empty, loading, and error states
- [x] #5 pnpm check, pnpm build, and pnpm test pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Tokens and fonts in index.css (Atkinson Hyperlegible Next/Mono, Literata), restyled shared/ui primitives, PLAN.md 10.3 spec, plainMath helper, then per-pane restyles (plan pane, evidence/source panes, trajectory) and the workspaces page.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reviewed with Playwright screenshots at 1440x900: workspaces page, research tab (all center and right views), trajectory. Opacity modifiers, color-mix, and oklch palette classes were removed from components.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Complete visual redesign on one solid-color token system; semantic tones restored; TeX questions readable. Verified with browser screenshots and pnpm check, pnpm build, pnpm test.
<!-- SECTION:FINAL_SUMMARY:END -->
