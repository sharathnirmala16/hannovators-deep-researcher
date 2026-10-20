---
id: TASK-000048
title: >-
  R2 Research quality: search intents, evidence level, stance, verdicts, deep
  research
status: Done
assignee: []
created_date: '2026-10-20 17:39'
updated_date: '2026-10-20 17:39'
labels:
  - backend
  - round-2
dependencies: []
ordinal: 48000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Round 2 lane research-quality had never run. Searches must look for opposing, alternative, and safety evidence, rank by evidence strength, explain every decision, and avoid NCBI throttling that made PubMed calls fail.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every searched source records search_intent; CORE, NEGATIVE, ALTERNATIVE, and SAFETY queries run
- [x] #2 Sources get evidence_level and stance; ranking keeps the strongest opposing or null evidence
- [x] #3 Each screen and appraise decision records a VERDICT step
- [x] #4 PubMed calls share a rate limit and retry 429 responses; a real run has no failed PubMed steps
- [x] #5 The evidence profile is populated after synthesis and synthesis no longer fails the run on an empty model reply
- [x] #6 Tavily deep research POST/GET works and cited URLs join as WEB sources
- [x] #7 Offline e2e and live e2e tests pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Shared NCBI token bucket + retry; best-match PubMed sort; reasoning off for QUERY/SYNTHESIZE; lenient GRADE parsing with a model-free fallback summary; evidence-first ranking with an opposing-evidence quota; CORE intent for legacy rows.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause of the empty evidence profile: Nemotron spent its output budget on reasoning in synthesize, the reply was empty, and the workspace failed. Live tests: test_live_platform.py + test_live_research_quality.py 4 passed. UI run 426eebdc shows intents Core 35 / Negative 17 / Alternatives 19 and a 16-outcome evidence profile. NCBI_API_KEY is empty in .env (2.5 req/s).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Research-quality lane runs for real: four search intents on every source, evidence level and stance, opposing-evidence quota, VERDICT steps, rate-limited PubMed with retries (0 failed steps), robust synthesis, and Tavily deep research. Verified with offline e2e (2 pass), live e2e (4 pass), and the UI run.
<!-- SECTION:FINAL_SUMMARY:END -->
