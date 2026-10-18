/**
 * Zod mirror of the Pydantic contracts in
 * `src/hannovators_deep_researcher/models/` (enums.py, contracts.py,
 * events.py). Keys stay snake_case, as on the wire (PLAN.md section 4.6).
 *
 * Every object is strict, like `ContractModel(extra="forbid")`. Fields with a
 * Pydantic default use `.default()`, so the input may omit them and the
 * decoded value always has them.
 */
import { z } from 'zod';

import {
  claimArmSchema,
  claimKindSchema,
  claimVerdictSchema,
  directnessSchema,
  evidenceLevelSchema,
  evidenceStanceSchema,
  gradeCertaintySchema,
  highlightMethodSchema,
  recommendationDirectionSchema,
  recommendationStrengthSchema,
  rejectionCodeSchema,
  requestedDomainModeSchema,
  robJudgementSchema,
  searchIntentSchema,
  sourceLinkKindSchema,
  sourceOriginSchema,
  sourceStatusSchema,
  stageIdSchema,
  traceEventKindSchema,
  uiComponentIdSchema,
  workspaceStatusSchema,
} from './enums';

export * from './enums';

// --- Shared field types (models/base.py) ------------------------------------

export const probability = z.number().min(0).max(1);
export const nonNegativeInt = z.int().min(0);
export const nonEmptyText = z.string().trim().min(1);
/** Pydantic `datetime`: ISO 8601, with or without a UTC offset. */
export const dateTime = z.iso.datetime({ offset: true, local: true });
export const stringList = z.array(z.string()).default(() => []);
export const nullableString = z.string().nullable().default(null);
/** `[x0, y0, x1, y1]` in PDF points. */
export const rect = z.tuple([z.number(), z.number(), z.number(), z.number()]);

// --- Decomposition ----------------------------------------------------------

const interventionComparisonPairSchema = z.strictObject({
  intervention: z.string(),
  comparison: z.string(),
});

export const picotsDecompositionSchema = z.strictObject({
  mode: z.literal('MEDICAL'),
  population: z.string(),
  interventions: stringList,
  comparisons: stringList,
  outcomes: stringList,
  timing: nullableString,
  study_designs: stringList,
  ic_pairs: z.array(interventionComparisonPairSchema).default(() => []),
});

export const scopeDecompositionSchema = z.strictObject({
  mode: z.literal('GENERAL'),
  entities: stringList,
  claims: stringList,
  metrics: stringList,
  time_horizon: nullableString,
  counter_hypotheses: stringList,
});

export const decompositionSchema = z.discriminatedUnion('mode', [
  picotsDecompositionSchema,
  scopeDecompositionSchema,
]);

// --- Synthesis --------------------------------------------------------------

const gradeAssessmentSchema = z.strictObject({
  certainty: gradeCertaintySchema,
  risk_of_bias: z.string(),
  inconsistency: z.string(),
  indirectness: z.string(),
  imprecision: z.string(),
  publication_bias: z.string(),
});

const pairwiseSummarySchema = z.strictObject({
  intervention: z.string(),
  comparison: z.string(),
  outcome: z.string(),
  summary: z.string(),
  source_ids: stringList,
  grade: gradeAssessmentSchema,
});

const recommendationSchema = z.strictObject({
  direction: recommendationDirectionSchema,
  strength: recommendationStrengthSchema,
  text: z.string(),
});

const provenanceSchema = z.strictObject({
  canary: z.string(),
  models: z.record(z.string(), z.string()).default(() => ({})),
  generated_at: dateTime,
});

export const synthesisSchema = z.strictObject({
  pairwise_summaries: z.array(pairwiseSummarySchema).default(() => []),
  analysis: z.string(),
  recommendation: recommendationSchema,
  provenance: provenanceSchema,
});

// --- Workspace --------------------------------------------------------------

export const workspaceSettingsSchema = z
  .strictObject({
    screen_votes_t: z.int().min(1).max(3).default(2),
    appraise_m: nonNegativeInt.default(2),
    screen_top_n: z.int().min(1).default(15),
    appraise_top_k: z.int().min(1).default(6),
    search_max_rounds: z.int().min(1).default(3),
    search_hits_min: nonNegativeInt.default(1),
    search_hits_max: z.int().min(1).default(5000),
    highlight_confidence_floor: probability.default(0.6),
    embedding_model: z.string().default('Qwen/Qwen3-Embedding-8B'),
    embedding_dimensions: z.int().min(32).max(4096).default(1024),
  })
  .refine((settings) => settings.search_hits_min <= settings.search_hits_max, {
    message: 'search_hits_min must not exceed search_hits_max',
  });

export const workspaceViewSchema = z.strictObject({
  id: z.string(),
  research_question: z.string(),
  domain_mode: requestedDomainModeSchema,
  status: workspaceStatusSchema,
  current_stage: stageIdSchema.nullable().default(null),
  auto_continue: z.boolean(),
  settings: workspaceSettingsSchema,
  error: nullableString,
  created_at: dateTime,
  updated_at: dateTime,
});

export const queryViewSchema = z.strictObject({
  id: z.string(),
  workspace_id: z.string(),
  iteration: nonNegativeInt,
  tool: z.string(),
  core_query: z.string(),
  applied_filters: z.string().default(''),
  raw_hit_count: nonNegativeInt.nullable().default(null),
  latency_ms: nonNegativeInt.nullable().default(null),
  refinement_note: nullableString,
  created_at: dateTime,
});

const rob2AssessmentSchema = z.strictObject({
  domains: z.record(z.string(), robJudgementSchema).default(() => ({})),
  overall: robJudgementSchema,
});

export const sourceViewSchema = z.strictObject({
  id: z.string(),
  origin: sourceOriginSchema,
  external_id: z.string(),
  title: z.string(),
  authors: stringList,
  year: z.int().nullable().default(null),
  venue: nullableString,
  url: nullableString,
  study_design: nullableString,
  status: sourceStatusSchema,
  screen_score: z.number().nullable().default(null),
  screen_z: z.number().nullable().default(null),
  screen_votes: nonNegativeInt.nullable().default(null),
  m_score: nonNegativeInt.nullable().default(null),
  directness: directnessSchema.nullable().default(null),
  rob2: rob2AssessmentSchema.nullable().default(null),
  rejection_code: rejectionCodeSchema.nullable().default(null),
  decision_explanation: nullableString,
  raw_url: nullableString,
  highlighted_url: nullableString,
  evidence_level: evidenceLevelSchema.nullable().default(null),
  evidence_rank: z.int().min(1).nullable().default(null),
  stance: evidenceStanceSchema.nullable().default(null),
  search_intent: searchIntentSchema.nullable().default(null),
  found_by: nullableString,
});

export const jsonRecord = z.record(z.string(), z.json()).default(() => ({}));

const funnelCount = nonNegativeInt.default(0);

export const funnelSchema = z.strictObject({
  seeds: funnelCount,
  raw: funnelCount,
  screen_promoted: funnelCount,
  screen_discounted: funnelCount,
  appraise_promoted: funnelCount,
  appraise_discounted: funnelCount,
  acquire_failed: funnelCount,
});

export const claimViewSchema = z.strictObject({
  id: z.string(),
  source_id: nullableString,
  kind: claimKindSchema,
  label: z.string(),
  text: z.string(),
  quote: nullableString,
  verdict: claimVerdictSchema,
  confidence: probability.nullable().default(null),
  outcome: nullableString,
  arm: claimArmSchema.nullable().default(null),
  highlight_ids: stringList,
});

export const highlightViewSchema = z.strictObject({
  id: z.string(),
  source_id: z.string(),
  claim_id: z.string(),
  page: z.int().min(1),
  rects: z.array(rect).default(() => []),
  method: highlightMethodSchema,
  score: z.number().nullable().default(null),
  color: z.string(),
  pdf_url: nullableString,
});

export const graphNodeSchema = z.strictObject({
  id: z.string(),
  label: z.string(),
  status: sourceStatusSchema,
  origin: sourceOriginSchema,
});

export const graphEdgeSchema = z.strictObject({
  source: z.string(),
  target: z.string(),
  kind: sourceLinkKindSchema,
});

export const graphViewSchema = z.strictObject({
  nodes: z.array(graphNodeSchema).default(() => []),
  edges: z.array(graphEdgeSchema).default(() => []),
});

/** The whole workspace view returned by `GET /api/workspaces/{id}`. */
export const workspaceStateSchema = z.strictObject({
  workspace: workspaceViewSchema,
  decomposition: decompositionSchema.nullable().default(null),
  queries: z.array(queryViewSchema).default(() => []),
  sources: z.array(sourceViewSchema).default(() => []),
  funnel: funnelSchema.default(() => funnelSchema.parse({})),
  claims: z.array(claimViewSchema).default(() => []),
  highlights: z.array(highlightViewSchema).default(() => []),
  synthesis: synthesisSchema.nullable().default(null),
  ui_components: z.array(uiComponentIdSchema).default(() => []),
  last_event_id: z.int().nullable().default(null),
});

// --- Trace events (models/events.py) ----------------------------------------

/** `id` is the `trace_events` autoincrement key and the SSE event ID. */
export const traceEventSchema = z.strictObject({
  id: z.int(),
  workspace_id: z.string(),
  stage: stageIdSchema,
  kind: traceEventKindSchema,
  message: z.string(),
  payload: z.record(z.string(), z.json()).default(() => ({})),
  created_at: dateTime,
});

// --- HTTP API bodies --------------------------------------------------------

/** Body of `POST /api/workspaces`. The server sets the embedding settings. */
export const createWorkspaceRequestSchema = z.strictObject({
  research_question: nonEmptyText,
  domain_mode: requestedDomainModeSchema.default('AUTO'),
  auto_continue: z.boolean().default(false),
  settings: workspaceSettingsSchema.nullable().default(null),
});

/** JSON body of `POST /api/workspaces/{id}/seeds`: exactly one of the keys. */
export const seedReferenceRequestSchema = z
  .strictObject({
    pmid: nonEmptyText.nullable().default(null),
    doi: nonEmptyText.nullable().default(null),
    url: nonEmptyText.nullable().default(null),
  })
  .refine(
    (seed) =>
      [seed.pmid, seed.doi, seed.url].filter((v) => v !== null).length === 1,
    { message: 'give exactly one of pmid, doi, or url' },
  );

/** Error body: `{"detail": {"code": "<UPPER_SNAKE>", "message": "<text>"}}`. */
export const apiErrorSchema = z.strictObject({
  detail: z.strictObject({
    code: z.string().regex(/^[A-Z][A-Z0-9_]*$/),
    message: z.string(),
  }),
});

// --- Types ------------------------------------------------------------------

export type Decomposition = z.infer<typeof decompositionSchema>;
export type PicotsDecomposition = z.infer<typeof picotsDecompositionSchema>;
export type ScopeDecomposition = z.infer<typeof scopeDecompositionSchema>;
export type Synthesis = z.infer<typeof synthesisSchema>;
export type WorkspaceSettings = z.infer<typeof workspaceSettingsSchema>;
export type WorkspaceView = z.infer<typeof workspaceViewSchema>;
export type QueryView = z.infer<typeof queryViewSchema>;
export type SourceView = z.infer<typeof sourceViewSchema>;
export type Funnel = z.infer<typeof funnelSchema>;
export type ClaimView = z.infer<typeof claimViewSchema>;
export type HighlightView = z.infer<typeof highlightViewSchema>;
export type GraphNode = z.infer<typeof graphNodeSchema>;
export type GraphEdge = z.infer<typeof graphEdgeSchema>;
export type GraphView = z.infer<typeof graphViewSchema>;
export type WorkspaceState = z.infer<typeof workspaceStateSchema>;
export type TraceEvent = z.infer<typeof traceEventSchema>;
/** Input shape: fields with a default may be omitted. */
export type CreateWorkspaceRequest = z.input<
  typeof createWorkspaceRequestSchema
>;
export type SeedReferenceRequest = z.input<typeof seedReferenceRequestSchema>;
export type ApiError = z.infer<typeof apiErrorSchema>;
