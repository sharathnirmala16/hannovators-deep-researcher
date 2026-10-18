---
id: TASK-000011
title: A3 Web search provider abstraction with auto mode (Tavily)
status: In Progress
assignee:
  - '@devin'
created_date: '2026-10-18 12:20'
updated_date: '2026-10-18 13:53'
labels:
  - phase-1
  - backend
  - 'lane:a3'
milestone: m-1
dependencies:
  - TASK-000001
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The project must work with any web search provider and survive provider failures during the demo. This ports the freesearch provider contract, resilience, and routing in slim form, with Tavily as the only provider for now (Exa and others are X4). High priority: time is short.

Spec: PLAN.md sections 1.1, 4.5, 5.1, 6, card "A3 websearch" in section 7.4. Reference: .archive/freesearch/src/freesearch/adapters/base.py, registry.py, services/routing.py, services/aggregation.py (canonicalize_url), infrastructure/resilience.py, adapters/tavily.py.
Early start: needs only P0.1 (Done). Parallel with: P0.3, P0.6, A5. May merge before Gate G0 (own files only).
Worktree: lane/a3-websearch
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Router supports auto, prefer, and require; auto follows WEB_SEARCH_PRIORITY and skips unconfigured or open-circuit providers
- [ ] #2 Primary 429 -> fallback answers and attempts lists both (test); all fail -> one typed error with each reason (test)
- [ ] #3 No configured provider -> clear startup error; pinned provider without a key -> error, no silent fallback (tests)
- [ ] #4 Tavily (search + extract via tavily-python) implements WebSearchProvider without freesearch quota, PAYGO, or usage bookkeeping
- [ ] #5 Priority names without a registered adapter (e.g. exa) are skipped with a startup warning
- [ ] #6 fetch uses only providers with supports_fetch; services/urls.py canonicalize_url strips tracking params, www., default ports, and fragments, and results are deduplicated by it (test)
- [ ] #7 Live checks: Tavily search (limit 3) and extract (one URL); auto picks Tavily
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. infrastructure/resilience.py: slim ResilientRunner (no httpx client, no redaction/telemetry). Retries retryable ProviderFailure and httpx.TransportError with capped exponential backoff + jitter; honors Retry-After carried by a RateLimited(ProviderFailure) subclass (gives up early when Retry-After > max_delay so the router fails over instead of stalling); per-provider circuit breaker (closed/open/half-open, one probe) with is_open(); CircuitOpenError(ProviderFailure). Injectable clock/sleeper/random for tests.
2. services/urls.py: canonicalize_url (lowercase host, strip www., default ports per scheme, fragment, trailing slash, utm_* and click-id params; sort query; http->https).
3. adapters/websearch/tavily.py: TavilyProvider (name, supports_fetch=True, is_configured) over AsyncTavilyClient with a client from infrastructure/http.py; search (limit<=20, include/exclude domains, days->start_date) and extract (markdown, max_chars truncation). Response hook records status + Retry-After; maps SDK errors to ProviderFailure (429 rate_limited retryable, 432/433 quota_exhausted, 401/403/400, timeout, 5xx, transport). No quota/PAYGO/usage code.
4. adapters/websearch/__init__.py: small registry {tavily: TavilyProvider.from_settings} + build_providers(settings) in WEB_SEARCH_PRIORITY order (plus a pinned name); unregistered names -> startup warning.
5. services/websearch_router.py: WebSearchRouter implementing the WebSearch port. Modes AUTO (priority order), PREFER (named provider first, then priority), REQUIRE (one provider, no fallback). Construction fails with WebSearchConfigError when no provider is configured, or when a required provider is unregistered or has no key. Chained failover through the runner, open-circuit providers SKIPPED, attempts recorded; all failed -> WebSearchUnavailable(ProviderFailure) with every reason. fetch uses supports_fetch providers only. Results deduplicated by canonicalize_url. create_web_search_router(settings, providers) maps WEB_SEARCH_PROVIDER (auto | name -> REQUIRE) for main.py.
6. Tests (card only): failover 429 (respx Tavily + in-test double, also checks dedupe), all-fail typed error, no configured provider at startup, pinned provider without key, canonicalize_url parametrized. Live: Tavily search limit 3, extract one URL, auto picks Tavily.
7. Checks, commit, rebase on origin/main, push, PR, finalize.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implementation decisions:
- Reference: .archive/freesearch is gitignored and missing from hdr_wt_3; with user approval it was read read-only from the main checkout.
- The router owns one ResilientRunner and wraps each provider call, so every adapter (and test doubles) gets retry + circuit breaking; adapters only map errors to ProviderFailure.
- Failover: auto/prefer move to the next provider on ANY ProviderFailure (not only retryable ones), so a Tavily 401/432 quota error also fails over during the demo. Retries within one provider happen only for retryable errors. Unexpected non-ProviderFailure exceptions propagate (bugs are not masked).
- Retry-After: carried by RateLimited(ProviderFailure) in infrastructure/resilience.py. A Retry-After above max_delay (10 s) stops retries at once so the router fails over instead of stalling.
- Modes: WEB_SEARCH_PROVIDER=auto -> AUTO; a provider name -> REQUIRE (pinned, no fallback). PREFER is available programmatically (WebSearchRouter(mode=PREFER, provider=...)); settings have no variable for it.
- Startup: WebSearchRouter construction raises WebSearchConfigError for no configured provider, or a pinned provider that is unregistered or has no key. build_providers() logs a warning for priority names without an adapter (verified in live log: 'exa' has no adapter).
- All providers failed -> WebSearchUnavailable(ProviderFailure), code all_providers_failed, message lists every provider: code: message, .attempts holds the ProviderAttempt list.

Notes for P0.5 / main.py wiring (not done here; main.py is frozen for this lane):
- router = create_web_search_router(settings, providers) with providers = build_providers(settings) from adapters/websearch.
- Contract note: the WebSearchProvider port has no aclose(). TavilyProvider.aclose() exists; the composition root should keep the provider list and close TavilyProvider instances on shutdown. Consider adding aclose() to the port in a contract fix.
- Contract note: ProviderError has no field for Retry-After; it travels on the RateLimited exception only, not on the wire (ProviderAttempt.error). That is enough for A3.

Validation: ruff format --check, ruff check, mypy (49 files), pytest (14 passed, 3 live deselected), uv build OK; pytest -m live: 3 passed (Tavily search limit 3, extract example.com, auto picks Tavily). pytest -m e2e exits 5 (no e2e tests on main yet; P0.5 adds tests/e2e).
<!-- SECTION:NOTES:END -->
