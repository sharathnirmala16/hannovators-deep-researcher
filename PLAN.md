# Implementation plan: Adaptive Deep Research & Evidence Synthesis Engine

This plan replaces the earlier "seed material storage" plan. It adapts the hackathon blueprint
(`architecture_planned_enhancements.md`) to the current scaffold and to the current provider stack.
Agents work in parallel git worktrees. Each lane owns a disjoint set of files.

Read sections 1 to 6 before you start a lane. Then read only your lane in section 7.

---

## 1. Decisions that change the blueprint

### 1.1 Provider stack

| Role | Provider and model |
| :--- | :--- |
| System-1 decisions (screening, span choice, UI routing, domain detection) | **Jev** through the **Command Code** Provider API: `POST https://api.commandcode.ai/provider/v1/systemone`, model `typesafe/jev-1.14.0` (pinned; `typesafe/jev` is the floating alias). Question types `choice`, `score`, `noul`. There is no other System-1 model. |
| Agent model (decompose, query rewrite, appraise, extract, synthesize) | **NVIDIA Nemotron 3.5 Super VL** on Nebius Token Factory (`nvidia/Nemotron-3.5-Super-VL`, OpenAI-compatible, 1M context, structured output, tool use, image input). One model for all roles. Each role can override the model ID by env var. |
| Embeddings | **Qwen3-Embedding-8B** on Nebius Token Factory (`Qwen/Qwen3-Embedding-8B`, 4096 dimensions native, MRL). Stored at `EMBEDDING_DIMENSIONS` (default 1024). Dense half of hybrid retrieval and the screening fallback. |
| Web search + extract | **Provider abstraction ported from `.archive/freesearch/`** with `auto` mode. Tavily is the only provider in A3. Exa and other providers are stretch work (X4). |
| Deep research report | **Tavily Research API** (`AsyncTavilyClient.research()` / `get_research()`, already in `tavily-python` 0.8.5, no new dependency). Tavily's research agents search, extract, and write a cited report. Its cited URLs join the candidate pool as `WEB` sources, so Jev screens them with the PubMed records. Stretch: the Nebius cookbook variant (`deepagents` + `langchain-nebius` + Tavily tool on Nemotron). |
| Literature | PubMed E-utilities (`esearch`/`efetch`/`elink`) + Europe PMC open-access PDFs. Semantic Scholar and Unpaywall are stretch work. |

Jev facts that shape the design (verify against the Command Code model page when you implement A2):

- One request has one `state` (text or JSON) and a map of named `questions`. Several questions share one request.
- Auth: `Authorization: Bearer <Command Code API key>`. Provider API access needs the GOAT plan or above.
- Context window: 32K tokens for the state plus the longest question. Truncate long states (abstracts, summaries).
- There is no batch, streaming, async job endpoint, or prompt cache. Screening 100 candidates means 100
  concurrent requests behind a semaphore. Command Code does not publish rate limits; honor `Retry-After`.
- Billing is per input token ($0.04/M); output is free. A 100-candidate screen costs well under one cent.
- Sources disagree on the `choice` option limit (25 or 255). Keep choice questions at 20 options or fewer.
  `score` takes an ordered criteria list. `noul` returns a float 0..1.
- Answers include `probabilities` and, for `choice` and `score`, `confidence`.
- Pin the model version, so thresholds tuned in I1 stay valid.

Qwen3-Embedding-8B facts:

- Matryoshka (MRL): any size from 32 to 4096. Request `dimensions=EMBEDDING_DIMENSIONS`. If the API
  returns a longer vector, keep the first N values and L2-normalize again. 1024 float32 = 4 KB per chunk.
- Instruction-aware: embed queries as `Instruct: <task>\nQuery: <text>`; embed documents with no prefix.
  Qwen reports a 1-5 % gain from task instructions. Write instructions in English.
- Store vectors L2-normalized, so cosine similarity is a dot product.
- Every workspace records `embedding_model` and `embedding_dimensions` in `settings_json` at creation.
  Retrieval refuses to compare vectors of different models or sizes.

Nemotron 3.5 Super VL facts: reasoning effort `none`/`high`; reasoning text can arrive in a separate
`reasoning_content` field; recommended sampling is temperature 1.0 (text) and 0.6 (vision), top_p 0.95.
The model was released on 2026-10-15. Expect structured-output quirks. Keep a JSON repair path.

### 1.2 How each model is used

| Use | Model | Shape |
| :--- | :--- | :--- |
| Domain auto-detect (`AUTO` mode) | Jev | `choice` {MEDICAL, GENERAL} on the research question. Keyword fallback. |
| PICOTS / scope decomposition with self-reflection + few-shot | Nemotron (role `DECOMPOSE`) | Draft -> critique -> revise, JSON schema output. |
| Query generation and hit-count refinement | Nemotron (role `QUERY`, effort `none`) | Core query + fixed standardized filters. |
| Stage-1 screening (T-threshold) | Jev | One request per candidate: one `score` (relevance 0..4), three `noul` votes, one `choice` (exclusion reason). |
| Screening fallback when Jev is down | Qwen3-Embedding-8B | Cosine similarity between the candidate and the decomposition text (embedded as a query with a screening instruction), then z-score. |
| Full-text M-matching, RoB 2, GRADE, claim verification | Nemotron (role `APPRAISE`, effort `high`) | JSON schema output with verbatim quotes. |
| Numerical extraction from table pages | Nemotron VL (role `EXTRACT_VISION`) | Page PNG rendered by PyMuPDF. Stretch lane X1. |
| Staged synthesis (pairwise -> analysis -> recommendation) | Nemotron (role `SYNTHESIZE`) | JSON schema output + provenance canary. |
| Claim -> PDF span | PyMuPDF `page.search_for(quote)` first, then Jev `choice` over at most 20 top hybrid-retrieval chunks | Highlight rectangles. |
| Adaptive UI routing | Jev | One request, one `noul` per UI component. A deterministic guard drops components with no data. |

### 1.3 Conflicts removed and features cut

| Blueprint feature | Decision | Reason |
| :--- | :--- | :--- |
| Per-workspace `workspace.db`, raw `shared/schema.sql`, `mmap_size` pragma | One database `data/hannovators.db`, SQLAlchemy models, Alembic revisions. | Matches the scaffold. One migration chain. |
| `data/seeds/<UUID>/` (old plan) and `papers/seeds|candidates|promoted|discounted/` folders | One folder per source: `data/workspaces/<workspace_id>/sources/<source_id>/`. Status lives in the database only. | Moving files on each status change breaks URLs and races with readers. |
| `rejection_audit.json`, `grade_profile.json`, `metadata.json`, `chunks.json` files | Database columns and tables. | One source of truth. |
| `graph.json` + NetworkX | `source_links` table. The API builds nodes and edges on request. | No sync between file and database. No extra dependency. |
| Six blueprint stages | Nine smaller stages (section 3). | Each stage is one lane. |
| `<PICOTSBuilder/>` and `<PICOTSAndSearchBuilder/>`; `<InteractivePRISMAFunnel/>` and `<SearchFunnelInspector/>` | One component each, with a `mode` variant. | Duplicate components. |
| Edit PICOTS chips "during retrieval" | Checkpoint after `decompose`. The user edits, then continues. `auto_continue=true` skips the checkpoint. | Editing during a run races the pipeline. |
| Several runs per workspace | One run per workspace. "Re-run" clones the workspace with its decomposition. | No `runs` table. |
| Sub-millisecond routing claims | Removed from UI copy. | Jev is a network call. |
| Multi-pass LLM CoT screening | Jev multi-question votes. LLM CoT for borderline records is stretch lane X3. | Cost and time. |
| Reflection Beam 1.0 | Removed. Per-role model overrides keep the option open. | One agent model. |
| Quicker meta-analysis (`rpy2` + R) | Cut. | Heavy dependency. |
| freesearch vault, quota ledger, OpenTelemetry store, MCP, control plane | Not ported. Keys come from env. | Not needed for the demo. |
| Behave BDD and Playwright-BDD | Deferred. Use pytest `e2e` tests and one plain Playwright smoke test. | See section 8. |

The archived Quicker copy has notebooks and benchmark data only. The `utils/` package with the
original prompts is missing. Write new prompts from the paper. Reuse the Quicker standardized PubMed
filters and the excluded publication-type list from `Phase2-literature_search.ipynb`.

---

## 2. Target code layout and ownership

Phase 0 creates every file below as a stub, so that lanes only fill in files they own.
`[P0]` = owned by Phase 0 and frozen after Gate G0. Other tags are lane IDs from section 7.

```text
src/hannovators_deep_researcher/
  main.py                              [P0] composition root: settings -> adapters -> services -> FastAPI app
  models/
    enums.py                           [P0] all enums in section 4.3
    contracts.py                       [P0] DTOs: decomposition, sources, claims, highlights, synthesis, WorkspaceState
    decisions.py                       [P0] Jev question/answer models
    web.py                             [P0] WebSearchRequest/Response, SearchResult, FetchedDocument, ProviderError
    literature.py                      [P0] CandidateRecord, SourceLinkRecord
    events.py                          [P0] TraceEvent
    ports.py                           [P0] Protocols in section 5.1
  configuration/
    database.py                        (exists)
    settings.py                        [P0] pydantic-settings, section 6
  infrastructure/
    database.py                        (exists)
    http.py                            [P0] shared httpx.AsyncClient factory
    resilience.py                      [A3] slim port of freesearch ResilientRunner (retry, Retry-After, circuit breaker)
    rate_limit.py                      [A4] async token bucket
  adapters/
    fake/                              [P0.5a] deterministic fakes for every port (offline mode + tests)
    nebius.py                          [A1] ChatModel + Embedder
    jev.py                             [A2] DecisionModel
    websearch/tavily.py                [A3] provider adapter (exa.py and others: X4)
    pubmed.py, europepmc.py            [A4] LiteratureSearch + open-access PDF lookup
  persistence/
    base.py                            (exists)
    tables.py                          [P0] SQLAlchemy tables, section 4.2
    repositories.py                    [P0] generic CRUD used by all stages
    queries/<lane>.py                  [lane] extra queries a lane needs (one new file per lane)
    migrations/versions/0002_core_schema.py [P0]
  services/
    ranking.py                         [P0] reciprocal_rank_fusion, z_scores (pure)
    urls.py                            [A3] canonicalize_url (pure; S3 imports it for dedupe)
    events.py                          [P0] DB-backed EventSink
    websearch_router.py                [A3] auto/prefer/require routing + chained failover
    documents/                         [A5] pdf_chunker, markdown_chunker, files (safe paths, download), highlighter, page_render
    retrieval/                         [A6] bm25, dense, hybrid, hierarchical
    workspace_state.py                 [A7] builds WorkspaceState and graph view
    pipeline/
      context.py                       [P0] StageContext
      orchestrator.py                  [P0] runs stages in order, status changes, checkpoint, failure capture
      stages/<stage>/__init__.py       [S1..S9] async def run(ctx: StageContext) -> None
  routers/
    __init__.py                        [P0] includes every router below
    workspaces.py, seeds.py, events.py, graph.py, health.py   [A7]

tests/
  unit/<package>/...                   [lane] edge-case tests listed in each lane
  integration/persistence/             [P0] migration + constraint tests
  integration/contract/                [P0] fixture JSON validates against WorkspaceState
  e2e/                                 [P0 skeleton, I1] pipeline through the HTTP API
  live/                                [lane] one cheap check per provider

frontend/src/
  app/                                 [P0] shell, providers, UI component registry (maps UiComponentId -> feature entry)
  domains/workspace/                   [F1] zod schemas, API client, SSE hook, event reducer (schemas are [P0])
  domains/evidence/                    [P0] selection store (claim -> highlight -> page), mappers
  features/workbench-shell/            [F1] 3-pane layout, new-run form, mode toggle, trace timeline
  features/scope-builder/              [F2] PICOTS chips (MEDICAL) / scope chips (GENERAL), continue button
  features/screening-funnel/           [F3] PRISMA-style funnel, query log, rejection audit
  features/evidence-table/             [F4] GRADE evidence profile (MEDICAL) / claim matrix (GENERAL), synthesis panel
  features/pdf-viewer/                 [F5] highlighted PDF in iframe at #page=N, web snapshot fallback
  features/citation-graph/             [F6] cytoscape graph of seeds, promoted, discounted, web
  shared/ui/                           [P0] shadcn primitives
  test/fixtures/workspace.medical.json, workspace.general.json   [P0, regenerated by I1]
```

Each feature folder exposes one entry component through `index.ts`. Phase 0 creates a placeholder
for each, and `app/` imports them once. Feature lanes never edit `app/`.

---

## 3. Pipeline

```text
POST /api/workspaces  ->  orchestrator (asyncio background task, one per workspace)
  1 ingest     seeds: PDF -> chunks(page, bbox); PMID -> PubMed record (+ OA PDF); URL -> web extract
  2 decompose  AUTO domain via Jev -> PICOTS (MEDICAL) or scope (GENERAL), self-reflection
               -> status AWAITING_REVIEW unless auto_continue  (user edits, POST /run continues)
  3 search     3-5 core queries + standardized filters; refine when hits == 0 or > 5000 (max 3 rounds);
               PubMed + web router + elink from seeds, concurrently -> sources(status RAW), search_queries
  4 screen     Jev per candidate (semaphore): relevance score + 3 votes + exclusion reason;
               promote when votes >= T (default 2), rank by z(relevance * confidence), keep top N (default 15)
  5 acquire    download OA PDFs / web snapshots -> chunks (ABSTRACT + FULLTEXT tiers) -> embeddings -> source_links
  6 appraise   MEDICAL: M-criteria match (M >= 2, INDIRECT when M == 2), RoB 2 checklist, metrics with verbatim quotes
               GENERAL: claim verification, credibility, contradictions
               promote top K (default 6)
  7 synthesize 3-step synthesis (pairwise -> analysis -> recommendation) + per-outcome GRADE + canary provenance
  8 highlight  each claim/metric quote -> page.search_for, fallback Jev choice over top chunks
               -> highlights rows + sources/<id>/highlighted.pdf
  9 compose    Jev noul per UI component + data guard -> workspaces.ui_components_json
Every stage emits trace_events. GET /api/workspaces/{id}/events streams them over SSE.
```

A stage failure marks the workspace `FAILED`, records the error in a `STAGE_FAILED` event, and keeps
all earlier data. Stages 3 to 7 must tolerate partial provider failure: log a `WARNING` event and continue.

---

## 4. Data

### 4.1 Files

```text
data/
  hannovators.db
  workspaces/<workspace_id>/sources/<source_id>/
    raw.pdf | snapshot.md
    highlighted.pdf
```

- The database stores paths relative to `data/`, with `/` separators: `workspaces/<ws>/sources/<src>/raw.pdf`.
- `services/documents/files.py` is the only module that turns a relative path into an absolute path.
  It rejects absolute paths, `..`, and any path outside `data/workspaces/`.
- FastAPI mounts `data/workspaces/` at `/files/`. Phase 0 replaces `data/seeds/.gitkeep` with
  `data/workspaces/.gitkeep` and updates `data/.gitignore`.

### 4.2 Tables (revision `0002_core_schema`)

All IDs are UUID strings unless noted. All `*_json` columns are TEXT holding JSON validated by a
Pydantic model in `models/`. Every table except `workspaces` has `workspace_id` with an FK and an index.

| Table | Columns |
| :--- | :--- |
| `workspaces` | `id`, `research_question`, `domain_mode`, `status`, `current_stage`, `auto_continue`, `settings_json` (T, M, top_n, top_k, max_rounds), `decomposition_json`, `synthesis_json`, `ui_components_json`, `error`, `created_at`, `updated_at` |
| `search_queries` | `id`, `workspace_id`, `iteration`, `tool` (`pubmed`, `web:<provider>`, `elink`), `core_query`, `applied_filters`, `raw_hit_count`, `latency_ms`, `refinement_note`, `created_at` |
| `sources` | `id`, `workspace_id`, `origin`, `external_id` (PMID, DOI, or canonical URL), `title`, `authors_json`, `year`, `venue`, `abstract`, `url`, `pdf_url`, `study_design`, `status`, `found_by_query_id`, `raw_path`, `highlighted_path`, `screen_score`, `screen_z`, `screen_votes`, `screen_json`, `m_score`, `directness`, `rob2_json`, `appraisal_json`, `rejection_code`, `decision_explanation`, `extra_json`, `created_at`. UNIQUE(`workspace_id`, `external_id`). |
| `source_links` | `id`, `workspace_id`, `from_source_id`, `to_source_id`, `kind` (`CITES`, `RELATED`, `SEED_MATCH`). UNIQUE(`from_source_id`, `to_source_id`, `kind`). |
| `chunks` | `id`, `workspace_id`, `source_id`, `tier` (`ABSTRACT`, `FULLTEXT`), `ordinal`, `page`, `bbox_json`, `text`, `embedding` (BLOB, L2-normalized float32, `EMBEDDING_DIMENSIONS` values), `token_count` |
| `claims` | `id`, `workspace_id`, `source_id` (nullable), `kind` (`METRIC`, `CLAIM`, `RECOMMENDATION`), `label` (e.g. "Intervention events/total"), `text`, `quote`, `verdict`, `confidence`, `payload_json` |
| `highlights` | `id`, `workspace_id`, `source_id`, `claim_id`, `chunk_id` (nullable), `page`, `rects_json`, `method` (`SEARCH`, `JEV_CHOICE`), `score`, `color` |
| `trace_events` | `id` INTEGER autoincrement (SSE cursor), `workspace_id`, `stage`, `kind`, `message`, `payload_json`, `created_at` |

Rule: no lane adds an Alembic revision. A lane that needs new data uses `extra_json`, `payload_json`,
or `appraisal_json`. If a real column is unavoidable, the integrator adds one serial revision on `main`
between phases, and lanes rebase.

### 4.3 Enums (`models/enums.py`)

- `DomainMode`: `MEDICAL`, `GENERAL` (the resolved mode; the decomposition discriminator)
- `RequestedDomainMode`: `MEDICAL`, `GENERAL`, `AUTO` (requests and `workspaces.domain_mode`; `AUTO` stays until decompose sets the resolved mode)
- `WorkspaceStatus`: `CREATED`, `RUNNING`, `AWAITING_REVIEW`, `COMPLETED`, `FAILED`
- `StageId`: `ingest`, `decompose`, `search`, `screen`, `acquire`, `appraise`, `synthesize`, `highlight`, `compose`
- `SourceOrigin`: `SEED`, `PUBMED`, `EUROPEPMC`, `WEB`
- `SourceStatus`: `SEED`, `RAW`, `SCREEN_PROMOTED`, `SCREEN_DISCOUNTED`, `APPRAISE_PROMOTED`, `APPRAISE_DISCOUNTED`, `ACQUIRE_FAILED`
- `RejectionCode`: `LOW_RELEVANCE`, `VOTES_BELOW_T`, `M_BELOW_THRESHOLD`, `ANIMAL_STUDY`, `REVIEW_OR_EDITORIAL`, `OFF_TOPIC`, `DUPLICATE`, `NO_FULL_TEXT`, `UNDERPOWERED`, `LOW_CREDIBILITY`
- `Directness`: `DIRECT`, `INDIRECT`
- `RobJudgement`: `LOW`, `SOME_CONCERNS`, `HIGH` (official RoB 2 levels)
- `GradeCertainty`: `HIGH`, `MODERATE`, `LOW`, `VERY_LOW`
- `ClaimKind`: `METRIC`, `CLAIM`, `RECOMMENDATION`
- `ClaimVerdict`: `SUPPORTED`, `CONTRADICTED`, `MIXED`, `UNVERIFIED`
- `UiComponentId`: `scope_builder`, `screening_funnel`, `evidence_profile_table`, `claim_matrix`, `synthesis_panel`, `pdf_viewer`, `citation_graph`
- `TraceEventKind`: `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED`, `PROGRESS`, `QUERY`, `DECISION`, `WARNING`, `STATUS`
- `ModelRole`: `DECOMPOSE`, `QUERY`, `APPRAISE`, `EXTRACT_VISION`, `SYNTHESIZE`
- Column and contract enums: `ChunkTier` (`ABSTRACT`, `FULLTEXT`), `SourceLinkKind` (`CITES`, `RELATED`, `SEED_MATCH`),
  `HighlightMethod` (`SEARCH`, `JEV_CHOICE`), `ClaimArm` (`INTERVENTION`, `COMPARISON`),
  `RecommendationDirection` (`FOR`, `AGAINST`, `NONE`), `RecommendationStrength` (`STRONG`, `CONDITIONAL`),
  `DecisionQuestionType` (`choice`, `score`, `noul`), `ProviderAttemptStatus` (`OK`, `FAILED`, `SKIPPED`)

All contracts extend `models/base.py` `ContractModel` (`extra="forbid"`), so unknown fields fail validation.

### 4.4 Key contracts (`models/contracts.py`)

- `Decomposition` = discriminated union on `mode`:
  - `PicotsDecomposition`: `population`, `interventions[]`, `comparisons[]`, `outcomes[]`, `timing`, `study_designs[]`, `ic_pairs[{intervention, comparison}]`
  - `ScopeDecomposition`: `entities[]`, `claims[]`, `metrics[]`, `time_horizon`, `counter_hypotheses[]`
- `Synthesis`: `pairwise_summaries[{intervention, comparison, outcome, summary, source_ids[], grade{certainty, risk_of_bias, inconsistency, indirectness, imprecision, publication_bias}}]`, `analysis`, `recommendation{direction: FOR|AGAINST|NONE, strength: STRONG|CONDITIONAL, text}`, `provenance{canary, models{}, generated_at}`. GENERAL mode uses the same shape: pairs become claim-versus-counter-claim. `grade.certainty` is a `GradeCertainty`; the five domain fields are short text judgements.
- `WorkspaceState` (one GET returns the whole view): `workspace`, `decomposition | null`, `queries[]`, `sources[]`, `funnel{seeds, raw, screen_promoted, screen_discounted, appraise_promoted, appraise_discounted, acquire_failed}`, `claims[]`, `highlights[]` (with `/files/...` URL + page), `synthesis | null`, `ui_components[]`, `last_event_id`.
- `TraceEvent`: `id`, `workspace_id`, `stage`, `kind`, `message`, `payload`, `created_at`.
- `WorkspaceSettings` (defaults): `screen_votes_t=2`, `appraise_m=2`, `screen_top_n=15`,
  `appraise_top_k=6`, `search_max_rounds=3`, `search_hits_min=1`, `search_hits_max=5000`,
  `highlight_confidence_floor=0.6`, `embedding_model` and `embedding_dimensions` (copied from settings
  at creation; read-only after creation).
- `WorkspaceView`: `id`, `research_question`, `domain_mode` (`RequestedDomainMode`), `status`, `current_stage`
  (nullable), `auto_continue`, `settings`, `error`, `created_at`, `updated_at`.
- `SourceView`: `id`, `origin`, `external_id`, `title`, `authors[]`, `year`, `venue`, `url`, `study_design`,
  `status`, `screen_score`, `screen_z`, `screen_votes`, `m_score`, `directness`, `rob2`
  (`{domains: {<domain>: RobJudgement}, overall: RobJudgement}` or null), `rejection_code`, `decision_explanation`,
  `raw_url` and `highlighted_url` (`/files/...` or null).
  The abstract is not in the state payload.
- `QueryView`: the `search_queries` columns.
- `ClaimView`: `id`, `source_id`, `kind`, `label`, `text`, `quote`, `verdict`, `confidence`, `outcome` (nullable),
  `arm` (`INTERVENTION`, `COMPARISON`, or null), `highlight_ids[]`.
- `HighlightView`: `id`, `source_id`, `claim_id`, `page`, `rects` (`[[x0, y0, x1, y1], ...]`), `method`,
  `score`, `color`, `pdf_url` (`/files/.../highlighted.pdf#page=N`, or null for web sources).
- `GraphView`: `nodes[{id, label, status, origin}]`, `edges[{source, target, kind}]`.
- `WorkspaceState.last_event_id` is null before the first event.
- API bodies: `CreateWorkspaceRequest` (`research_question`, `domain_mode` default `AUTO`, `auto_continue` default
  false, `settings` nullable; the server sets the embedding fields), `SeedReferenceRequest` (exactly one of `pmid`,
  `doi`, `url`), `ApiError` (section 4.6). `DECOMPOSITION_ADAPTER` parses `decomposition_json`.

### 4.5 Port data shapes

- `DecisionQuestion`: `type` (`choice` | `score` | `noul`), `instructions`, `criteria`
  (`dict[str, str | None]` with 1 to 20 options for choice, `list[str]` with at least 2 levels for score,
  optional `{"true": str, "false": str}` for noul). The model rejects other shapes.
- `DecisionAnswer`: `type`, `choice` (str | null), `score` (float | null), `noul` (float | null),
  `confidence` (float | null), `probabilities` (`dict[str, float]`).
- `WebSearchRequest`: `query`, `limit` (default 10), `include_domains[]`, `exclude_domains[]`, `days` (nullable).
- `SearchResult`: `title`, `url`, `snippet`, `published_at` (nullable), `score` (0..1, nullable), `provider`.
- `WebSearchResponse`: `query`, `results[]`, `provider`, `attempts[{provider, status: ProviderAttemptStatus, latency_ms, error: ProviderError | null}]`.
- `FetchedDocument`: `url`, `title` (nullable), `content` (markdown or text), `content_type`, `provider`.
- `ProviderError`: `provider`, `code`, `message`, `retryable`, `status_code`. Adapters raise
  `ProviderFailure(error: ProviderError)` (`models/web.py`), so routers and stages can fail over on one exception type.
- `CandidateRecord`: `origin`, `external_id`, `title`, `abstract`, `authors[]`, `year`, `venue`, `doi`,
  `pmid`, `pmcid`, `url`, `pdf_url`, `publication_types[]`.
- `SourceLinkRecord`: `from_external_id`, `to_external_id`, `kind`.

### 4.6 Wire formats

- API errors: HTTP status + `{"detail": {"code": "<UPPER_SNAKE>", "message": "<text>"}}`.
- SSE frame: `id: <trace_events.id>`, `event: trace`, `data: <TraceEvent JSON>`, blank line.
  Heartbeat: a `: ping` comment line. After the final `STATUS` event, the server sends `event: end` and closes.
- JSON uses `snake_case` on the wire. The frontend keeps `snake_case` in zod schemas and maps in domain mappers if needed.

---

## 5. Interfaces

### 5.1 Ports (`models/ports.py`)

```python
class ChatModel(Protocol):
    async def complete_json[T: BaseModel](
        self,
        *,
        role: ModelRole,
        system: str,
        user: str,
        schema: type[T],
        images: Sequence[bytes] = (),
    ) -> T: ...


class Embedder(Protocol):
    model: str
    dimensions: int

    # instruction=None -> document embedding; a task instruction -> query embedding.
    # Returns L2-normalized vectors of length `dimensions`.
    async def embed(
        self, texts: Sequence[str], *, instruction: str | None = None
    ) -> list[list[float]]: ...


class DecisionModel(Protocol):
    async def evaluate(
        self, state: str, questions: Mapping[str, DecisionQuestion]
    ) -> dict[str, DecisionAnswer]: ...


class WebSearch(Protocol):  # implemented by services/websearch_router.py
    async def search(self, request: WebSearchRequest) -> WebSearchResponse: ...
    async def fetch(self, url: str, *, max_chars: int = 50_000) -> FetchedDocument: ...


class WebSearchProvider(Protocol):  # implemented by each adapters/websearch/*.py
    name: str
    supports_fetch: bool

    def is_configured(self) -> bool: ...
    async def search(self, request: WebSearchRequest) -> WebSearchResponse: ...
    async def fetch(self, url: str, *, max_chars: int) -> FetchedDocument: ...


class LiteratureSearch(Protocol):
    async def count(self, query: str) -> int: ...
    async def search(self, query: str, *, limit: int) -> list[CandidateRecord]: ...
    async def related(
        self, external_ids: Sequence[str], *, limit: int
    ) -> list[SourceLinkRecord]: ...
    async def open_access_pdf_url(self, record: CandidateRecord) -> str | None: ...


class EventSink(Protocol):
    async def emit(
        self,
        workspace_id: str,
        stage: StageId,
        kind: TraceEventKind,
        message: str,
        payload: Mapping[str, object] | None = None,
    ) -> None: ...
```

`StageContext` (`services/pipeline/context.py`) carries: `workspace_id`, `settings`, a session factory,
`repositories`, `chat`, `embedder`, `decisions`, `web`, `literature`, `events`. Stages call
`services/documents` and `services/retrieval` directly.

`PROVIDER_MODE=fake` makes `main.py` wire `adapters/fake/*` for every port. Fakes are deterministic and
return plausible data, so the full pipeline and the frontend run offline:

- `FakeChatModel.complete_json(schema=...)` returns `schema.fake_example()` when the schema class defines
  that classmethod, else it raises. Each stage defines its own LLM response schemas inside its stage
  package, each with `fake_example()`. Stage lanes never edit `adapters/fake/`.
- `FakeDecisionModel` answers any question from a hash of `(state, question key)`: stable, varied, valid.
- `FakeEmbedder` returns L2-normalized hashed bag-of-words vectors of length `EMBEDDING_DIMENSIONS`,
  so similar text scores higher.
- `FakeWebSearch` and `FakeLiteratureSearch` serve a canned medical and general candidate set
  (about 40 records each) from `adapters/fake/data/`, plus one small text-layer PDF for downloads.

### 5.2 HTTP API (`/api`)

| Method + path | Purpose |
| :--- | :--- |
| `POST /workspaces` | `{research_question, domain_mode: MEDICAL|GENERAL|AUTO, auto_continue, settings?}` -> workspace. Does not start the run. |
| `POST /workspaces/{id}/seeds` | Multipart PDF, or JSON `{pmid}` / `{doi}` / `{url}` -> source row with status `SEED` |
| `POST /workspaces/{id}/run` | Start, or continue from `AWAITING_REVIEW`. 409 when already running. |
| `PUT /workspaces/{id}/decomposition` | Replace the decomposition. Allowed only in `AWAITING_REVIEW`. |
| `POST /workspaces/{id}/clone` | New workspace with the same question, seeds, and decomposition |
| `GET /workspaces/{id}` | `WorkspaceState` |
| `GET /workspaces/{id}/events` | SSE. Event `id` = `trace_events.id`. Honors `Last-Event-ID`. Heartbeat every 15 s. Closes after `COMPLETED`/`FAILED`. |
| `GET /workspaces/{id}/graph` | `{nodes[], edges[]}` from `sources` + `source_links` |
| `GET /health/providers` | Configured providers and the result of a cheap ping for each |
| `GET /files/...` | Static files from `data/workspaces/` |

SSE uses a plain `StreamingResponse` that tails `trace_events` by ID. No extra dependency. This works
across reconnects and survives a browser reload.

---

## 6. Configuration (`configuration/settings.py`, `.env.example`)

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `PROVIDER_MODE` | `real` | `fake` = offline fakes for every port |
| `API_HOST` | `127.0.0.1` | |
| `API_PORT` / `VITE_PORT` | none (required) | Main repository `8001` / `5174`; worktree slot N uses `8001 + 10N` / `5174 + N` (AGENTS.md). A missing port stops the launch. |
| `NEBIUS_API_KEY` | - | Required in `real` mode |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1/` | |
| `AGENT_MODEL` | `nvidia/Nemotron-3.5-Super-VL` | Default for every `ModelRole` |
| `MODEL_<ROLE>` | - | Optional per-role override, e.g. `MODEL_APPRAISE` |
| `EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-8B` | |
| `EMBEDDING_DIMENSIONS` | `1024` | MRL size, 32 to 4096. Changing it needs new workspaces (old vectors do not compare). |
| `JEV_API_KEY` | - | A Command Code API key with Provider API access |
| `JEV_BASE_URL` | `https://api.commandcode.ai/provider/v1` | The adapter posts to `{JEV_BASE_URL}/systemone`. Any System One compatible host works. |
| `JEV_MODEL` | `typesafe/jev-1.14.0` | Pinned. `typesafe/jev` floats to the latest release. |
| `JEV_CONCURRENCY` | `8` | Semaphore for per-candidate requests |
| `JEV_MAX_STATE_TOKENS` | `24000` | Budget below the 32K context; the adapter truncates longer states |
| `WEB_SEARCH_PROVIDER` | `auto` | `auto`, or one provider name to pin it |
| `WEB_SEARCH_PRIORITY` | `tavily,exa` | Order for `auto`. Names without a registered adapter (Exa until X4) are skipped with a startup warning. |
| `TAVILY_API_KEY`, `EXA_API_KEY` | - | A provider without a key is skipped in `auto` |
| `NCBI_API_KEY`, `NCBI_EMAIL` | - | Raises the PubMed limit from 3 to 10 requests/s |
| `RUN_BUDGET_MAX_CANDIDATES` | `100` | Hard cap on screened candidates per run |

Never log key values. `GET /health/providers` reports only "configured" or "missing".

---

## 7. Phases and lanes

### 7.1 Worktree protocol

1. Create a worktree per lane from the current `main` in a free slot (1 to 9):
   `scripts\windows\create_worktree.bat lane/<lane> <slot>` (e.g. `lane/a3-websearch 3`).
   The worktree lands in `..\hdr_wt_<slot>`. Delete it after merge with
   `scripts\windows\delete_worktree.bat <slot>`, then reuse the slot.
2. The script copies the main `.env`, writes the slot's `API_PORT` and `VITE_PORT` (AGENTS.md table),
   installs backend and frontend, and migrates the worktree's own `data/hannovators.db`.
3. Edit only the files your lane owns (section 2 and the lane card). Create new files only inside your
   owned folders, or as `persistence/queries/<lane>.py`.
4. Do not edit frozen `[P0]` files, `pyproject.toml`, `uv.lock`, `frontend/package.json`,
   `frontend/pnpm-lock.yaml`, or migrations. If you need a contract or dependency change, stop and
   ask the integrator for a small "contract fix" commit on `main`, then rebase.
5. Before merge: rebase on `main`, run the checks in `AGENTS.md`, run your lane's tests, and run
   `uv run pytest -m e2e` (offline). Merge order inside a phase does not matter because files are disjoint.
6. One integrator (human or agent) merges, reruns all checks on `main`, and runs the gate.

### 7.2 Phase map

```text
Phase 0  foundation           P0.1 -> P0.3 -> P0.4 -> P0.5          (backend chain, on main)
                              P0.1 -> P0.5a (fakes) -> P0.5
                              P0.2 (anytime)  ;  P0.1 -> P0.6 ;  P0.2 + P0.6 -> P0.7   (frontend)
                              P0.5 also needs P0.6 (contract test reads the fixtures)
         Gate G0
Phase 1  leaves (fully parallel)       A1 A2 A3 A4 A5 A6 A7  ||  F1 F2 F3 F4 F5 F6
         Gate G1
Phase 2  stages (fully parallel)       S1 .. S9  ||  F7 (live wiring)
         Gate G2
Phase 3  integration                   I1 (first, on main)  ->  I2 I3 I4 (parallel)
         Gate G3 = demo ready
Phase 4  stretch (independent, any order)   X1 .. X6
```

Phase 0 parallelism: after P0.1, run P0.3 (backend) and P0.6 (frontend) in two worktrees; P0.2 can
run from the start. Stage lanes (Phase 2) may start right after G0 against fakes, but merge only after
G1 so they can tune prompts and thresholds against real adapters.

Early start: A3 (Tavily) and A5 (documents) need only P0.1 (ports, settings, `respx`, markers). They
run in parallel with the rest of Phase 0 and may merge before G0, because they add only their own
files. P0.5 then skips stubs for modules that already exist. A1, A2, and A4 can also start early when
capacity allows. A6 waits for P0.4 (`ranking.py`); A7 and the F-lanes wait for G0.

### 7.3 Phase 0: foundation

Phase 0 cards edit `[P0]` files, so they run on `main` (or short-lived branches merged right away).

**P0.1 backend contracts** (first; blocks P0.3 and P0.6)
- Add all backend dependencies at once so later lanes never touch the lockfile: `fastapi`,
  `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `httpx`, `openai`, `tavily-python`, `pymupdf`,
  `rank-bm25`, `numpy`, `python-multipart`, `defusedxml`; dev: `respx`. Prefer versions published at
  least 7 days ago.
- Register pytest markers `live` and `e2e`; default `addopts` deselects `live`.
- `models/enums.py`, `contracts.py`, `decisions.py`, `web.py`, `literature.py`, `events.py`, `ports.py`
  exactly as sections 4.3 to 4.6 and 5.1. `configuration/settings.py` and `.env.example` per section 6.
  `infrastructure/http.py`.
- Tests: none required beyond import and type checks.

**P0.2 frontend dependencies and dev server** (no dependencies; parallel with everything in Phase 0)
- Add `zod`, `cytoscape`, and shadcn primitives (button, card, badge, tabs, table, input, textarea,
  dialog, tooltip, scroll-area, progress, separator, resizable, sonner) in one change.
- `vite.config.ts` reads `VITE_PORT` and `API_PORT` from the root `.env` with `loadEnv(mode, rootDir, '')`
  (shell environment wins); proxies `/api` and `/files` to `http://127.0.0.1:${API_PORT}`; serves on
  `VITE_PORT` with `strictPort: true`; fails with a clear message when either port is missing.

**P0.3 persistence** (needs P0.1)
- `persistence/tables.py`, revision `0002_core_schema` (section 4.2), `persistence/repositories.py`
  (create/get/list/update helpers per table, `update_source_fields(id, **fields)`, `list_sources(ws, statuses)`,
  `append_event`, `events_after(ws, last_id)`).
- Replace `data/seeds/.gitkeep` with `data/workspaces/.gitkeep`; update `data/.gitignore`.
- Tests: migration upgrade/downgrade expects the new tables; UNIQUE(`workspace_id`, `external_id`) rejects a duplicate.

**P0.4 pipeline core** (needs P0.3)
- `services/ranking.py` (RRF, z-scores), `services/events.py` (DB-backed `EventSink`),
  `services/pipeline/context.py`, `orchestrator.py` (stage order from section 3, status changes, checkpoint
  after `decompose`, resume, failure capture), one stub package per `StageId` (emits "not implemented").
- Tests: z-scores with zero variance and with one item; RRF with empty lists and ties; orchestrator stops
  at `AWAITING_REVIEW` and resumes; a stage exception sets `FAILED` and keeps earlier events.

**P0.5a fake adapters** (needs P0.1 only; parallel with P0.3, P0.4, P0.6)
- `adapters/fake/*` and `adapters/fake/data/` per section 5.1: `FakeChatModel` (`fake_example()` lookup),
  `FakeDecisionModel` (hash-based, valid answers for any question), `FakeEmbedder` (normalized hashed
  bag-of-words, `EMBEDDING_DIMENSIONS` long), `FakeWebSearch` and `FakeLiteratureSearch` (canned medical
  and general sets of about 40 records each, OA PDF URLs that resolve to one small text-layer PDF).
  Each fake satisfies its `models/ports.py` Protocol under mypy. No wiring into `main.py` (P0.5 does that).
- Tests: a schema without `fake_example()` raises a clear error; the same input gives the same Jev answer,
  and every `choice` answer is one of the given options; similar texts score higher than unrelated
  texts and every vector has unit norm.

**P0.5 app skeleton** (needs P0.4, P0.5a, and P0.6)
- Wire `adapters/fake/*` (from P0.5a) when `PROVIDER_MODE=fake`; stub modules (raise `NotImplementedError`)
  for every A-lane file that does not exist yet; never overwrite a lane module that is already merged
  (A3 and A5 may land first); wire merged real adapters in `main.py`; `routers/*` stubs (501) except a minimal working `POST /workspaces`,
  `POST /run`, and SSE needed by the e2e test; `main.py` composition root; `/files` mount.
- `tests/e2e/test_pipeline_offline.py`: create workspace -> run -> SSE until `COMPLETED`.
- `tests/integration/contract/test_fixtures.py`: both frontend fixtures validate as `WorkspaceState`.
- Console script `hdr-api` in `pyproject.toml` (`hannovators_deep_researcher.main:run`): runs uvicorn on
  `API_HOST`/`API_PORT` from settings, accepts `--host`/`--port` overrides, and stops with a clear error
  when no port is configured (no numeric fallback, as in freesearch `require_transport_port`).
- README: run commands (`uv run hdr-api`, `PROVIDER_MODE=fake`).

**P0.6 frontend contract and fixtures** (needs P0.1; parallel with P0.3 to P0.4)
- `domains/workspace/api/schema.ts`: zod mirrors of section 4 (`WorkspaceState`, `TraceEvent`, `GraphView`, enums).
- Hand-write `test/fixtures/workspace.medical.json`, `workspace.general.json`, and `graph.*.json` with
  realistic data (about 40 sources, 6 promoted, claims with quotes, highlights, synthesis).
- Tests: the zod schema accepts all fixtures; it rejects an unknown `TraceEventKind`.

**P0.7 frontend shell** (needs P0.2 and P0.6)
- `domains/workspace/`: typed API client and SSE hook stubs; `VITE_USE_FIXTURES=1` serves the fixtures.
- `domains/evidence/`: selection store (selected claim -> highlight -> source + page) provided in `app/`.
- `app/`: 3-pane shell; registry that renders feature entries from `ui_components`; one placeholder
  entry per feature folder (section 2), so feature lanes never edit `app/`.

**Gate G0**: all checks pass on `main`; `uv run alembic upgrade head` works on a fresh database; the
offline e2e test passes; all fixtures pass the pytest and Vitest contract checks; `pnpm dev` with
fixtures shows the shell with placeholder panes. After G0, `[P0]` files are frozen.

### 7.4 Phase 1: leaves (parallel)

Each card lists: owned files, work, required edge-case tests, live checks, done-when.

**A1 nebius** - `adapters/nebius.py`, `tests/unit/adapters/test_nebius.py`, `tests/live/test_nebius.py`
- `ChatModel` via the `openai` SDK with `base_url`; `response_format` JSON schema from the Pydantic model;
  strip `reasoning_content`; on invalid JSON, one repair retry, then raise a typed error. Map
  `ModelRole` to model ID, reasoning effort, and temperature. Accept images as base64 data URLs.
- `Embedder` for `Qwen/Qwen3-Embedding-8B`: batches of at most 64 texts; sends `dimensions`; when the
  response is longer, keeps the first `EMBEDDING_DIMENSIONS` values (MRL) and L2-normalizes again;
  formats queries as `Instruct: <instruction>\nQuery: <text>` and documents with no prefix;
  float32 BLOB pack/unpack helpers.
- Tests: fenced or truncated JSON is repaired or fails clearly; a role override env var wins; empty
  embedding input returns `[]` without a call; a 4096-value response becomes 1024 values with unit norm;
  the instruction prefix appears only when `instruction` is set.
- Live: one tiny JSON completion; one embedding of two strings whose length equals `EMBEDDING_DIMENSIONS`.

**A2 jev** - `adapters/jev.py`, `tests/unit/adapters/test_jev.py`, `tests/live/test_jev.py`
- `DecisionModel` over httpx against the Command Code Provider API (`{JEV_BASE_URL}/systemone`,
  model `JEV_MODEL`); Bearer auth with `JEV_API_KEY`; semaphore `JEV_CONCURRENCY`; timeouts; typed
  errors for 401/402/403 (plan without Provider API)/429/5xx. Validate that every requested question key
  comes back. Truncate a state above `JEV_MAX_STATE_TOKENS` (estimate 4 chars per token) and reject a
  `choice` question with more than 20 options.
- Tests: missing answer key; `choice` value outside the given options; `noul` exactly 0.5; 429 with
  `Retry-After`; an over-long state is truncated, not sent whole; 21 choice options -> error before any call.
- Live: one request with one `choice`, one `score`, and one `noul` question.

**A3 websearch** (early start after P0.1; high priority) - `infrastructure/resilience.py`,
`adapters/websearch/tavily.py`, `services/websearch_router.py`, `services/urls.py`, matching tests
- Port from `.archive/freesearch/` and keep it slim: `ResilientRunner` (retry on 429/5xx/transport
  errors, `Retry-After`, per-provider circuit breaker); Tavily only (search + extract) through
  `tavily-python`, dropping freesearch quota, PAYGO, and usage bookkeeping. Router modes: `auto`
  (priority order, skip unconfigured, unregistered, or open-circuit providers, chained failover on
  retryable errors), `prefer`, `require`. `fetch` uses only providers with `supports_fetch`.
  `services/urls.py`: `canonicalize_url`; dedupe results by canonical URL. Exa and others come in X4.
- Tests (failover uses a second in-test provider double): primary returns 429 -> fallback answers and
  the trace lists both; all providers fail -> one typed error with each provider's reason; no configured
  provider -> clear error at startup; pinned provider without a key -> error, no silent fallback;
  `canonicalize_url` strips tracking params, `www.`, default ports, and fragments.
- Live: Tavily search (limit 3) and extract (one URL); `auto` picks Tavily.

**T1 tavily-research** (demo lane; needs P0.1 and A3) - `adapters/tavily_research.py`,
`services/deep_research.py`, `models/deep_research.py` (new file), `routers/deep_research.py`, matching tests
- `build_deep_research(settings, http)`: `AsyncTavilyClient.research(input, model="mini", citation_format="numbered",
  output_schema=None)`, then poll `get_research(request_id)` every few seconds until `completed` or `failed`
  (timeout about 3 minutes).
- `POST /api/workspaces/{id}/deep-research` starts a background run: input = research question plus the
  decomposition summary when one exists (MEDICAL adds clinicaltrials.gov, fda.gov, ema.europa.eu, who.int
  as preferred domains). It emits PROGRESS events (stage `search`) when it starts, while polling, and when it
  finishes. It stores `{status, content, sources[], started_at, finished_at, error}` at
  `data/workspaces/<ws>/deep_research.json` through `services/documents/files.py`. It inserts each cited source
  as a `WEB` source with status `RAW` and `extra_json.found_by = "tavily_research"`, deduplicated by
  `canonicalize_url`. `GET /api/workspaces/{id}/deep-research` returns that record.
- The API lane includes `routers.deep_research` through a guarded import. The frontend shows a
  "Tavily deep research" panel in the workbench shell.
- Tests: a failed research task sets status `failed` and the run continues; a cited URL that duplicates an
  existing source is not inserted twice.
- Live: one `model="mini"` research call on a short question.

**A4 literature** - `infrastructure/rate_limit.py`, `adapters/pubmed.py`, `adapters/europepmc.py`, matching tests
- PubMed `esearch` (count and IDs), `efetch` XML -> `CandidateRecord` (title, abstract with labelled
  sections, authors, year, journal, DOI, PMCID, publication types), `elink` related/cited-by. Drop the
  Quicker excluded publication types. Europe PMC open-access PDF URL lookup by PMID/PMCID.
- Tests: record without abstract; structured abstract sections joined in order; malformed XML raises a
  typed error; rate limiter never exceeds the limit in a burst.
- Live: `count` for a fixed query > 0; `efetch` of one known PMID; OA URL for one known open-access PMCID.

**A5 documents** - `services/documents/*`, matching tests
- `files.py`: safe relative paths (section 4.1), streaming download with size cap and content-type check.
- `pdf_chunker.py`: PyMuPDF text blocks -> paragraph chunks with `page` and `bbox`; first-page abstract -> `ABSTRACT` tier.
- `markdown_chunker.py`: heading-aware chunks for web snapshots (no bbox).
- `highlighter.py`: given `(page, rects, color)` items, write `highlighted.pdf` with highlight annotations.
- `page_render.py`: page -> PNG bytes for the VL model.
- Tests: `..`, absolute, and drive-letter paths rejected; PDF without a text layer -> zero chunks and a
  flag (not an exception); rects outside the page are clipped; download over the size cap aborts.

**A6 retrieval** - `services/retrieval/*`, matching tests
- BM25 over chunk tokens; dense dot product over normalized float32 BLOBs with numpy (the query is
  embedded with a retrieval instruction); hybrid via `ranking.reciprocal_rank_fusion`;
  `hierarchical_retrieve(question, source_ids, rewrite)`: abstract tier -> top 5 full-text chunks ->
  one query rewrite through `ChatModel` when the best score is below a threshold.
- Tests: empty corpus; one-chunk corpus; a source with abstract only; the rewrite runs at most once;
  stored vectors with a different size or model than the workspace settings -> typed error.

**A7 api** - `routers/workspaces.py`, `seeds.py`, `events.py`, `graph.py`, `health.py`, `services/workspace_state.py`, matching tests
- Endpoints in section 5.2. Background run task through the orchestrator. SSE tail with `Last-Event-ID` and heartbeat.
- Tests: SSE resumes after `Last-Event-ID` with no duplicates; `run` while running -> 409; `PUT
  decomposition` outside `AWAITING_REVIEW` -> 409; seed upload of a non-PDF -> 415; graph with no links.

**F1 workbench-shell** - `features/workbench-shell/`, `domains/workspace/` (except `schema.ts`)
- New-run form (question, mode `AUTO`/`MEDICAL`/`GENERAL`, seeds upload, auto-continue), API client,
  SSE hook with reconnect, event reducer, live trace timeline, status header, clone button.
- Tests: reducer ignores duplicate event IDs; reducer handles out-of-order IDs; reconnect sends the last ID.

**F2 scope-builder** - `features/scope-builder/`
- PICOTS chips (MEDICAL) and scope chips (GENERAL): add, edit, delete; I-C pairs; save via `PUT`;
  "Continue" via `POST /run`. Read-only after the checkpoint.

**F3 screening-funnel** - `features/screening-funnel/`
- PRISMA-style funnel from `funnel` counts; MEDICAL labels (records, screened, full text, included)
  and GENERAL labels; query log with hit counts and refinement notes; rejection audit list (code,
  explanation, link to the source).

**F4 evidence-table** - `features/evidence-table/`
- MEDICAL: GRADE evidence profile per outcome; RoB 2 traffic lights per study; metric cells such as
  `2/70 vs 8/53` that set the selection (claim -> highlight). GENERAL: claim matrix with verdict,
  confidence, sources, contradictions. Synthesis panel: pairwise summaries -> analysis -> recommendation, provenance tag.

**F5 pdf-viewer** - `features/pdf-viewer/`
- `iframe` of `highlighted.pdf#page=N` (or `raw.pdf`) for the selected highlight; source list switcher;
  web sources show the snapshot text with the quote marked.

**F6 citation-graph** - `features/citation-graph/`
- cytoscape graph from `GET /graph`; node color by status (seed, promoted, discounted, web); click
  selects a source for the PDF viewer.

Frontend feature lanes F2 to F6 have no required tests. Add a test only for a pure helper with a real edge case.

**Gate G1**: every A-lane live check passes with real keys (`uv run pytest -m live`); the offline e2e
test still passes; every feature renders both fixtures without console errors.

### 7.5 Phase 2: stages (parallel)

Each stage lane owns `services/pipeline/stages/<stage>/` (prompts, domain variants, logic),
`persistence/queries/<stage>.py` if needed, and `tests/unit/services/pipeline/stages/test_<stage>.py`.
Put MEDICAL and GENERAL variants in `medical.py` and `general.py` inside the stage package.

**S1 ingest** - Resolve seeds: PDF -> chunks; PMID/DOI -> PubMed record + OA PDF if any; URL -> web
extract -> markdown chunks. Embed chunks. Tests: duplicate seed (same PMID twice) -> one source; a seed
URL that fails to fetch -> `WARNING`, run continues.

**S2 decompose** - `AUTO` domain detection (Jev `choice`, keyword fallback). PICOTS or scope with
few-shot examples (2-3 per mode, in the package) + self-reflection (draft -> critique -> revise). Use
seed abstracts as context. Then checkpoint. Tests: Jev failure -> keyword fallback; an empty
comparison list is valid; several I-C pairs survive the round trip.

**S3 search** - Generate 3-5 core queries (P + I focus; omit C/O when they over-restrict) + standardized
filters (MEDICAL: Quicker RCT filter, `NOT review[pt]`, humans). Refine when `count == 0` or `> 5000`,
at most `max_rounds`. Run PubMed, the web router, and `elink` from seeds concurrently. Insert `RAW`
sources (dedupe by `external_id`), `search_queries`, `source_links`. Cap at `RUN_BUDGET_MAX_CANDIDATES`.
Tests: the refinement loop stops at `max_rounds`; 0 hits -> broadened query logged with a note; a
duplicate across PubMed and web -> one source; one provider down -> others still return.

**S4 screen** - One Jev request per candidate (state = decomposition summary + title + abstract):
`relevance` score 0..4, three `noul` votes (MEDICAL: population, intervention, design eligible;
GENERAL: entity, claim, credibility), `exclusion` choice. Promote when votes >= T, rank by
z(relevance x confidence), keep top N; set `rejection_code` and `decision_explanation` for the rest.
Embedding fallback when Jev fails. Tests: fewer candidates than N; all candidates tie; votes exactly
at T; Jev failure for one candidate -> that candidate uses the fallback score.

**S5 acquire** - For `SCREEN_PROMOTED`: OA PDF or web snapshot -> files -> chunks -> embeddings.
No full text -> abstract-only chunks and a `NO_FULL_TEXT` note (not a rejection by itself). `elink`
for promoted PMIDs -> `CITES`/`RELATED` links. Tests: download failure -> `ACQUIRE_FAILED` with a
reason; abstract-only source still has an `ABSTRACT` chunk.

**S6 appraise** - Per promoted source, via `hierarchical_retrieve`:
MEDICAL: M-criteria match (P, I, C, O); M >= threshold keeps (INDIRECT when M == 2), otherwise
`M_BELOW_THRESHOLD`; RoB 2 with explicit signaling questions for all five domains (randomization,
deviations, missing data, measurement, selective reporting); metrics as `METRIC` claims with verbatim
`quote` (events/total per arm, effect, CI).
GENERAL: claims as `CLAIM` rows with verdict, credibility, conflict-of-interest flag, contradictions.
Keep the top K as `APPRAISE_PROMOTED`; the rest get `APPRAISE_DISCOUNTED` with a code and explanation.
Tests: M exactly at threshold -> INDIRECT; RoB 2 overall equals the worst domain; a quote not found in
the retrieved text is marked `UNVERIFIED`; an LLM failure for one source -> `WARNING`, other sources continue.

**S7 synthesize** - From `APPRAISE_PROMOTED` sources and their claims: pairwise summaries per I-C pair
and outcome (GENERAL: claim versus counter-claim) with per-outcome GRADE (start HIGH for RCTs, LOW for
observational; downgrade for risk of bias, inconsistency, indirectness incl. M == 2, imprecision,
publication bias) -> integrated analysis -> active-voice directional recommendation based on evidence
only, with cost and preference considerations listed separately. Write `synthesis_json` with the
provenance canary and model IDs, plus one `RECOMMENDATION` claim. Tests: zero promoted sources ->
"insufficient evidence" synthesis instead of failure; every `source_ids` entry refers to a promoted
source; GRADE never rises above the study-design start level.

**S8 highlight** - For each claim with a quote: `page.search_for(quote)` (normalize whitespace and
hyphenation); else hybrid-retrieve top chunks and ask Jev `choice` for the best one, accept above
`highlight_confidence_floor`. Write highlights and one `highlighted.pdf` per source; colors by claim
kind. Tests: a quote split across lines is found; a quote not found and Jev below the floor -> no
highlight, claim kept; a web source -> highlight row with no PDF rects.

**S9 compose** - One Jev request: state = compact workspace summary; one `noul` per `UiComponentId`.
Guard: drop components with no data; always keep `scope_builder` and `screening_funnel`; MEDICAL ->
`evidence_profile_table`, GENERAL -> `claim_matrix` when the data exists. Fallback = guard-only rules.
Tests: Jev down -> fallback set; a component with no data is never mounted.

**F7 live wiring** (frontend, parallel with the stage lanes; needs A7 and F1 merged) - Point the
domain API client and SSE hook at the real backend running with `PROVIDER_MODE=fake`; make every
feature work with live data and partial states (running, awaiting review, failed); keep fixture mode
working. Owns `domains/workspace/` and may touch feature `model/` files only to fix decoding.
Tests: reducer edge case for a `STAGE_FAILED` event followed by a reconnect.

**Gate G2**: `PROVIDER_MODE=fake` e2e produces a non-empty funnel, claims, highlights, synthesis, and
UI components; one live e2e run each for a MEDICAL and a GENERAL question completes within the
candidate budget (`uv run pytest -m "live and e2e"`); the frontend shows a full fake-mode run live.

### 7.6 Phase 3: integration

**I1 integrate** (first, on `main`, one agent) - Tune thresholds and prompts on two demo questions;
fix cross-lane issues; regenerate both frontend fixtures from real runs; set the frontend to the live
API by default; extend `tests/e2e/` with the live e2e test. Contract fixes happen here.

Then in parallel:

- **I2 demo-replay** - `scripts/` + `services/replay.py`: export a completed workspace (database rows +
  files) to a bundle and import it; `DEMO_REPLAY=<bundle>` replays its trace events over SSE with the
  original timing. This protects the demo from network failure.
- **I3 smoke + docs** - Add `@playwright/test`; one smoke test in fixture mode (new run -> funnel ->
  click a metric cell -> PDF viewer shows the page). Exclude `tests/**` in `vitest.config.ts` so
  Vitest does not pick up the Playwright spec. Update README and AGENTS.md commands.
- **I4 design pass** - Apply the `frontend-design` skill to the shell and features. No behavior changes.

**Gate G3 (demo ready)**: checks green; live e2e passes; replay bundle plays offline; smoke test passes.

### 7.7 Phase 4: stretch (independent lanes)

- **X1 VL tables** - Detect table pages (PyMuPDF `find_tables`), send the page PNG to the VL role for
  numeric extraction, cross-check against the text quote.
- **X2 more literature** - Semantic Scholar and Unpaywall adapters behind `LiteratureSearch`.
- **X3 borderline CoT** - LLM chain-of-thought screening only for candidates with votes == T - 1.
- **X4 more web providers** - Brave, Firecrawl, You.com adapters from freesearch; optional fanout + RRF.
- **X5 ask** - `POST /workspaces/{id}/ask`: user question -> hierarchical retrieval -> answer with highlights.
- **X6 benchmark** - Score screening against Q2CRBench-3 included studies (non-commercial data-use terms apply).

### 7.8 Backlog tickets and sessions

Every card above is one Backlog.md task, sized for one agent session. Milestones are the phases.
Task dependencies encode the order. Labels: `phase-N`, `backend` or `frontend`, `lane:<id>`
(e.g. `lane:a3`), `gate`, `stretch`.

| Phase | Cards -> tasks |
| :--- | :--- |
| 0 | P0.1 `TASK-000001`, P0.2 `-02`, P0.3 `-03`, P0.4 `-04`, P0.6 `-05`, P0.5 `-06`, P0.7 `-07`, Gate G0 `-08`, P0.5a `-45` |
| 1 | A1-A7 `-09` to `-15`, F1-F6 `-16` to `-21`, Gate G1 `-22` |
| 2 | S1-S9 `-23` to `-31`, F7 `-32`, Gate G2 `-33` |
| 3 | I1 `-34`, I2 `-35`, I3 `-36`, I4 `-37`, Gate G3 `-38` |
| 4 | X1-X6 `-39` to `-44` |

Find work that can run now:

```sh
backlog task list --status "To Do" --plain     # then pick tasks whose dependencies are Done
backlog task list --labels phase-1 --plain
backlog task view TASK-<n> --plain
```

Start a session for one task with this prompt:

> Implement Backlog task TASK-<n>. Follow `AGENTS.md`. Read `PLAN.md` sections 1 to 6, then the card
> named in the task. Work in the worktree for its lane. Record your plan in the task before you code.

Rules:

- The task links to its card. The card and sections 1 to 6 are the full specification. Deeper
  planning happens in the session and goes into the task plan, not into this file.
- If a session changes a contract, `PLAN.md` must change in the same commit (integrator only).
- A gate task is done only when all its acceptance criteria pass on `main`.

---

## 8. Test policy (hackathon)

- Write tests only for: edge cases in pure logic (boundaries, empty inputs, malformed external
  payloads, failover, path safety); one cheap live check per external provider; a few end-to-end tests
  of the critical path. Each lane card lists its required tests.
- No tests for trivial happy paths, DTOs, wiring, layout, or styling. No snapshots. No coverage targets.
- Markers: `unit`, `integration`, `live`, `e2e`. Default `uv run pytest` skips `live`.
  `uv run pytest -m live` runs live checks; they skip when a key is missing.
- Mock HTTP with `respx` at the adapter boundary. Use `adapters/fake/` for ports in service and e2e tests.
- Live checks make one small request each. No loops. No extra retries.
- Behave and Playwright-BDD are deferred. Phase 3 adds one plain Playwright smoke test.

---

## 9. Risks and fallbacks

| Risk | Fallback |
| :--- | :--- |
| Command Code does not publish Jev rate limits; no batch endpoint | Semaphore, `Retry-After`, budget cap, embedding-score fallback in S4, guard-only fallback in S9 |
| Jev 32K context or choice-option limit exceeded | Adapter truncates states and rejects choice questions above 20 options |
| Embedding size changed mid-project | Size and model stored per workspace; retrieval refuses mixed vectors; new workspaces pick up the new size |
| Nemotron 3.5 Super VL is new; JSON quirks | JSON repair retry; strip reasoning text; per-role model override |
| Few open-access PDFs | Abstract tier + web snapshots; highlights only where a PDF exists |
| PDF without text layer | Abstract tier now; VL extraction in X1 |
| PubMed throttling | Token bucket; `NCBI_API_KEY` |
| A web provider fails during the demo | `auto` failover; replay bundle (I2) |
| Windows paths | `pathlib` everywhere; POSIX relative paths in the database |
| Merge conflicts | Pre-created stubs, frozen `[P0]` files, per-lane query modules, no lane migrations or lockfile edits |
