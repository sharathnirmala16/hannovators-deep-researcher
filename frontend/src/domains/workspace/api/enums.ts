/**
 * Zod mirror of `src/hannovators_deep_researcher/models/enums.py`.
 * Import these through `./schema`, which re-exports them.
 */
import { z } from 'zod';

export const domainModeSchema = z.enum(['MEDICAL', 'GENERAL']);
export const requestedDomainModeSchema = z.enum(['MEDICAL', 'GENERAL', 'AUTO']);
export const workspaceStatusSchema = z.enum([
  'CREATED',
  'RUNNING',
  'AWAITING_REVIEW',
  'COMPLETED',
  'FAILED',
]);
/** Pipeline stages in run order. */
export const stageIdSchema = z.enum([
  'ingest',
  'decompose',
  'search',
  'screen',
  'acquire',
  'appraise',
  'synthesize',
  'highlight',
  'compose',
]);
export const sourceOriginSchema = z.enum([
  'SEED',
  'PUBMED',
  'EUROPEPMC',
  'WEB',
]);
export const sourceStatusSchema = z.enum([
  'SEED',
  'RAW',
  'SCREEN_PROMOTED',
  'SCREEN_DISCOUNTED',
  'APPRAISE_PROMOTED',
  'APPRAISE_DISCOUNTED',
  'ACQUIRE_FAILED',
]);
export const rejectionCodeSchema = z.enum([
  'LOW_RELEVANCE',
  'VOTES_BELOW_T',
  'M_BELOW_THRESHOLD',
  'ANIMAL_STUDY',
  'REVIEW_OR_EDITORIAL',
  'OFF_TOPIC',
  'DUPLICATE',
  'NO_FULL_TEXT',
  'UNDERPOWERED',
  'LOW_CREDIBILITY',
]);
export const directnessSchema = z.enum(['DIRECT', 'INDIRECT']);
/** Official RoB 2 judgement levels. */
export const robJudgementSchema = z.enum(['LOW', 'SOME_CONCERNS', 'HIGH']);
export const gradeCertaintySchema = z.enum([
  'HIGH',
  'MODERATE',
  'LOW',
  'VERY_LOW',
]);
export const claimKindSchema = z.enum(['METRIC', 'CLAIM', 'RECOMMENDATION']);
export const claimVerdictSchema = z.enum([
  'SUPPORTED',
  'CONTRADICTED',
  'MIXED',
  'UNVERIFIED',
]);
export const claimArmSchema = z.enum(['INTERVENTION', 'COMPARISON']);
export const uiComponentIdSchema = z.enum([
  'scope_builder',
  'screening_funnel',
  'evidence_profile_table',
  'claim_matrix',
  'synthesis_panel',
  'pdf_viewer',
  'citation_graph',
]);
export const traceEventKindSchema = z.enum([
  'STAGE_STARTED',
  'STAGE_COMPLETED',
  'STAGE_FAILED',
  'PROGRESS',
  'QUERY',
  'DECISION',
  'WARNING',
  'STATUS',
]);
/** Agent model roles. Each role can override the model ID with MODEL_<ROLE>. */
export const modelRoleSchema = z.enum([
  'DECOMPOSE',
  'QUERY',
  'APPRAISE',
  'EXTRACT_VISION',
  'SYNTHESIZE',
]);
export const chunkTierSchema = z.enum(['ABSTRACT', 'FULLTEXT']);
export const sourceLinkKindSchema = z.enum(['CITES', 'RELATED', 'SEED_MATCH']);
export const highlightMethodSchema = z.enum(['SEARCH', 'JEV_CHOICE']);
export const recommendationDirectionSchema = z.enum(['FOR', 'AGAINST', 'NONE']);
export const recommendationStrengthSchema = z.enum(['STRONG', 'CONDITIONAL']);
/** Jev System One question types. */
export const decisionQuestionTypeSchema = z.enum(['choice', 'score', 'noul']);
/** Outcome of one provider attempt inside a routed web search. */
export const providerAttemptStatusSchema = z.enum(['OK', 'FAILED', 'SKIPPED']);
/** Study design on the evidence hierarchy (`evidence_rank` 1 = strongest). */
export const evidenceLevelSchema = z.enum([
  'META_ANALYSIS',
  'SYSTEMATIC_REVIEW',
  'RCT',
  'NON_RANDOMIZED_TRIAL',
  'COHORT',
  'CASE_CONTROL',
  'CROSS_SECTIONAL',
  'CASE_SERIES',
  'GUIDELINE',
  'NARRATIVE_REVIEW',
  'PRECLINICAL',
  'WEB_REPORT',
  'OTHER',
]);
export const evidenceStanceSchema = z.enum([
  'SUPPORTS',
  'OPPOSES',
  'NULL_RESULT',
  'MIXED',
  'ALTERNATIVE',
  'UNCLEAR',
]);
export const searchIntentSchema = z.enum([
  'CORE',
  'NEGATIVE',
  'ALTERNATIVE',
  'SAFETY',
  'SEED_CITATION',
  'DEEP_RESEARCH',
]);
export const trajectoryActorSchema = z.enum(['AGENT', 'USER', 'SYSTEM']);
export const trajectoryKindSchema = z.enum([
  'STAGE',
  'LLM',
  'DECISION',
  'SEARCH',
  'FETCH',
  'DOWNLOAD',
  'EMBED',
  'RETRIEVE',
  'VERDICT',
  'USER_ACTION',
  'CHAT',
]);
export const trajectoryStatusSchema = z.enum([
  'RUNNING',
  'OK',
  'ERROR',
  'SKIPPED',
]);
export const verdictOutcomeSchema = z.enum(['KEPT', 'REMOVED', 'FLAGGED']);
export const chatRoleSchema = z.enum(['USER', 'ASSISTANT']);

export type DomainMode = z.infer<typeof domainModeSchema>;
export type RequestedDomainMode = z.infer<typeof requestedDomainModeSchema>;
export type WorkspaceStatus = z.infer<typeof workspaceStatusSchema>;
export type StageId = z.infer<typeof stageIdSchema>;
export type SourceOrigin = z.infer<typeof sourceOriginSchema>;
export type SourceStatus = z.infer<typeof sourceStatusSchema>;
export type RejectionCode = z.infer<typeof rejectionCodeSchema>;
export type Directness = z.infer<typeof directnessSchema>;
export type RobJudgement = z.infer<typeof robJudgementSchema>;
export type GradeCertainty = z.infer<typeof gradeCertaintySchema>;
export type ClaimKind = z.infer<typeof claimKindSchema>;
export type ClaimVerdict = z.infer<typeof claimVerdictSchema>;
export type ClaimArm = z.infer<typeof claimArmSchema>;
export type UiComponentId = z.infer<typeof uiComponentIdSchema>;
export type TraceEventKind = z.infer<typeof traceEventKindSchema>;
export type ModelRole = z.infer<typeof modelRoleSchema>;
export type ChunkTier = z.infer<typeof chunkTierSchema>;
export type SourceLinkKind = z.infer<typeof sourceLinkKindSchema>;
export type HighlightMethod = z.infer<typeof highlightMethodSchema>;
export type RecommendationDirection = z.infer<
  typeof recommendationDirectionSchema
>;
export type RecommendationStrength = z.infer<
  typeof recommendationStrengthSchema
>;
export type DecisionQuestionType = z.infer<typeof decisionQuestionTypeSchema>;
export type ProviderAttemptStatus = z.infer<typeof providerAttemptStatusSchema>;
export type EvidenceLevel = z.infer<typeof evidenceLevelSchema>;
export type EvidenceStance = z.infer<typeof evidenceStanceSchema>;
export type SearchIntent = z.infer<typeof searchIntentSchema>;
export type TrajectoryActor = z.infer<typeof trajectoryActorSchema>;
export type TrajectoryKind = z.infer<typeof trajectoryKindSchema>;
export type TrajectoryStatus = z.infer<typeof trajectoryStatusSchema>;
export type VerdictOutcome = z.infer<typeof verdictOutcomeSchema>;
export type ChatRole = z.infer<typeof chatRoleSchema>;
