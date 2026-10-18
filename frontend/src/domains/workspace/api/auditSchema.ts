/**
 * Zod mirror of the audit and research contracts: source detail, workspace
 * list, trajectory (models/trajectory.py), chat (models/chat.py), and deep
 * research (models/deep_research.py). Same rules as `./schema`.
 */
import { z } from 'zod';

import {
  chatRoleSchema,
  requestedDomainModeSchema,
  stageIdSchema,
  trajectoryActorSchema,
  trajectoryKindSchema,
  trajectoryStatusSchema,
  verdictOutcomeSchema,
  workspaceStatusSchema,
} from './enums';
import {
  dateTime,
  jsonRecord,
  nonEmptyText,
  nonNegativeInt,
  nullableString,
  probability,
  rect,
  sourceViewSchema,
  stringList,
} from './schema';

/** `GET /api/workspaces/{id}/sources/{source_id}`. */
export const sourceDetailSchema = z.strictObject({
  source: sourceViewSchema,
  abstract: nullableString,
  pdf_url: nullableString,
  screen: jsonRecord,
  appraisal: jsonRecord,
  extra: jsonRecord,
  chunk_count: nonNegativeInt.default(0),
  claim_ids: stringList,
  trajectory_step_ids: z.array(z.int()).default(() => []),
});

/** One row of `GET /api/workspaces` (newest first). */
export const workspaceSummarySchema = z.strictObject({
  id: z.string(),
  research_question: z.string(),
  domain_mode: requestedDomainModeSchema,
  status: workspaceStatusSchema,
  current_stage: stageIdSchema.nullable().default(null),
  created_at: dateTime,
  updated_at: dateTime,
  source_count: nonNegativeInt.default(0),
  promoted_count: nonNegativeInt.default(0),
  seed_count: nonNegativeInt.default(0),
});

// --- Trajectory (models/trajectory.py) --------------------------------------

/** One row of the trajectory (network-tab) table. `id` is also the cursor. */
export const trajectoryStepSummarySchema = z.strictObject({
  id: z.int().min(1),
  workspace_id: z.string(),
  parent_id: z.int().nullable().default(null),
  actor: trajectoryActorSchema,
  kind: trajectoryKindSchema,
  stage: stageIdSchema.nullable().default(null),
  name: z.string(),
  target: nullableString,
  status: trajectoryStatusSchema,
  started_at: dateTime,
  ended_at: dateTime.nullable().default(null),
  duration_ms: nonNegativeInt.nullable().default(null),
  summary: z.string().default(''),
  source_ids: stringList,
  outcome: verdictOutcomeSchema.nullable().default(null),
  confidence: probability.nullable().default(null),
  error: nullableString,
});

/** A step with request and response bodies (`GET .../trajectory/{step_id}`). */
export const trajectoryStepSchema = trajectoryStepSummarySchema.extend({
  request: jsonRecord,
  response: jsonRecord,
});

export const trajectoryPageSchema = z.strictObject({
  steps: z.array(trajectoryStepSummarySchema).default(() => []),
  next_after: z.int().nullable().default(null),
  total: nonNegativeInt.default(0),
});

/** Body of `POST /api/workspaces/{id}/trajectory/actions`. */
export const userActionRequestSchema = z.strictObject({
  name: nonEmptyText,
  summary: z.string().default(''),
  target: nullableString,
  source_ids: stringList,
  details: jsonRecord,
});

// --- Chat (models/chat.py) --------------------------------------------------

/** Citation `[n]`: `rects` are PDF points on the 1-based `page`. */
export const citationSchema = z.strictObject({
  n: z.int().min(1),
  source_id: z.string(),
  source_title: z.string(),
  chunk_id: nullableString,
  page: z.int().min(1).nullable().default(null),
  rects: z.array(rect).default(() => []),
  quote: z.string(),
  pdf_url: nullableString,
  url: nullableString,
});

export const chatMessageViewSchema = z.strictObject({
  id: z.string(),
  workspace_id: z.string(),
  role: chatRoleSchema,
  content: z.string(),
  citations: z.array(citationSchema).default(() => []),
  trajectory_step_id: z.int().nullable().default(null),
  created_at: dateTime,
});

export const chatRequestSchema = z.strictObject({ question: nonEmptyText });

// --- Deep research (models/deep_research.py) --------------------------------

export const deepResearchRecordSchema = z.strictObject({
  status: z.enum(['pending', 'running', 'completed', 'failed']),
  content: z.string().default(''),
  sources: z
    .array(
      z.strictObject({
        title: z.string(),
        url: z.string(),
        source_id: nullableString,
      }),
    )
    .default(() => []),
  started_at: dateTime.nullable().default(null),
  finished_at: dateTime.nullable().default(null),
  error: nullableString,
});

export type SourceDetail = z.infer<typeof sourceDetailSchema>;
export type WorkspaceSummary = z.infer<typeof workspaceSummarySchema>;
export type TrajectoryStepSummary = z.infer<typeof trajectoryStepSummarySchema>;
export type TrajectoryStep = z.infer<typeof trajectoryStepSchema>;
export type TrajectoryPage = z.infer<typeof trajectoryPageSchema>;
export type UserActionRequest = z.input<typeof userActionRequestSchema>;
export type Citation = z.infer<typeof citationSchema>;
export type ChatMessageView = z.infer<typeof chatMessageViewSchema>;
export type DeepResearchRecord = z.infer<typeof deepResearchRecordSchema>;
