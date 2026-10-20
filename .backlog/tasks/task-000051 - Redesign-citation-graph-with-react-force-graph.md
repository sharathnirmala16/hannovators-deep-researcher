---
id: TASK-000051
title: Redesign citation graph with react-force-graph
status: Done
assignee:
  - '@devin'
created_date: '2026-10-20 18:48'
updated_date: '2026-10-20 19:09'
labels:
  - frontend
dependencies: []
ordinal: 51000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The cytoscape concentric graph in the Source pane reads as cluttered and static: every label is drawn at once, rings are implicit, and the selected source is hard to find. A force-directed canvas (react-force-graph-2d) that keeps the seed-to-outer tier semantics and the annotated-paper design tokens should make the graph legible and pleasant to explore.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Graph renders with react-force-graph-2d; cytoscape is removed from dependencies
- [x] #2 Seeds sit at the center, included sources on the next orbit, web and excluded sources further out, with visible tier guides
- [x] #3 Clicking a node selects the source; the selected node uses the marker highlight and stays in sync with selection from other panes
- [x] #4 Hovering a node highlights its neighbours and shows its title, status, and link count
- [x] #5 Zoom in, zoom out, and fit controls work; labels for minor nodes appear only when zoomed in or focused
- [x] #6 Reduced motion renders a settled layout without animation
- [x] #7 pnpm check, pnpm build, and pnpm test pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Design (annotated paper, frontend-design pass): faint orbit guides drawn on the canvas mark the evidence tiers (seed core, Included, Web, Excluded) and a radial d3 force holds each node on its orbit. Shape and fill carry status without relying on hue: seeds = blue stamp with inner ring, included = solid green, web = violet diamond, excluded = hollow grey, unappraised = hollow dashed. Yellow marker halo + marked label only for the selected source; hover/focus dims everything outside the neighbourhood with solid shade colors. Labels: seeds and included always, others when zoomed in or focused. No particles, no glow, no dark canvas; settle once, reduced motion renders pre-settled.
1. Replace cytoscape with react-force-graph-2d + d3-force (radial, collide).
2. model/: graph data mapper, palette/tier constants, canvas painters (nodes, orbits), element-size and reduced-motion hooks.
3. ui/: GraphCanvas (force graph wiring, selection sync), GraphControls (zoom in/out/fit), GraphReadout (focused source card), legend with shape swatches.
4. Update README/PLAN mentions, run pnpm check/build/test, screenshot review via subagent.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified in the browser against a live 103-source workspace: orbit layout, hover neighbourhood and readout, click and cross-pane selection with off-screen pan, zoom in/out/fit, reduced motion paints a settled layout. Review subagent findings applied: stale click guard reset, memoized link accessors. Kept on purpose: resize refits the view; markerEdge #e6c63a matches the Wordmark; the readout shadow uses the allowed rgba(24,34,58,a) form. pnpm check, pnpm build, pnpm test pass.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Replaced the cytoscape concentric graph with react-force-graph-2d and d3-force. Each tier sits on a labelled orbit, and shape plus color show status. Labels avoid each other and the canvas edge. The marker highlight shows the selected source. Hover fades the graph outside the source's neighbourhood and shows a readout card. Added zoom controls. Reduced motion is respected. Verified with a manual browser run and pnpm check, build, and test.
<!-- SECTION:FINAL_SUMMARY:END -->
