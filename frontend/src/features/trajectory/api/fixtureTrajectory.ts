/**
 * Fixture mode (`VITE_USE_FIXTURES=1`) for the trajectory. The shared fixture
 * client serves an empty trajectory, so this loader serves the recorded
 * `src/test/fixtures/trajectory.<name>.json` files instead (lazy glob, like the
 * shared fixture client). The last steps of a fixture arrive on a simulated
 * live stream: first RUNNING, then closed.
 */
import { z } from 'zod';

import type {
  TrajectoryPage,
  TrajectoryQuery,
  TrajectoryStep,
  TrajectoryStepSummary,
  TrajectoryStreamHandlers,
} from '@/domains/workspace';

import { ACTORS, KINDS, OUTCOMES, STAGES } from '../model/vocabulary';

const loaders = import.meta.glob<unknown>(
  '/src/test/fixtures/trajectory.*.json',
  {
    import: 'default',
  },
);

const nullableText = z.string().nullable();

const stepSchema = z.strictObject({
  id: z.int().min(1),
  workspace_id: z.string(),
  parent_id: z.int().nullable(),
  actor: z.enum(ACTORS),
  kind: z.enum(KINDS),
  stage: z.enum(STAGES).nullable(),
  name: z.string(),
  target: nullableText,
  status: z.enum(['RUNNING', 'OK', 'ERROR', 'SKIPPED']),
  started_at: z.string(),
  ended_at: nullableText,
  duration_ms: z.int().min(0).nullable(),
  summary: z.string(),
  source_ids: z.array(z.string()),
  outcome: z.enum(OUTCOMES).nullable(),
  confidence: z.number().min(0).max(1).nullable(),
  error: nullableText,
  request: z.record(z.string(), z.json()),
  response: z.record(z.string(), z.json()),
}) satisfies z.ZodType<TrajectoryStep>;

const fixtureSchema = z.strictObject({
  workspace_id: z.string(),
  steps: z.array(stepSchema),
});

/** Steps at the end of a fixture that arrive on the simulated stream. */
const STREAMED_TAIL = 8;
const STREAM_GAP_MS = 900;

let fixtures: Promise<z.infer<typeof fixtureSchema>[]> | undefined;

function loadFixtures() {
  fixtures ??= Promise.all(
    Object.values(loaders).map(async (load) =>
      fixtureSchema.parse(await load()),
    ),
  );
  return fixtures;
}

/** The recorded steps of a workspace, or null when no fixture has them. */
export async function fixtureSteps(
  workspaceId: string,
): Promise<readonly TrajectoryStep[] | null> {
  const all = await loadFixtures();
  return all.find((item) => item.workspace_id === workspaceId)?.steps ?? null;
}

function summaryOf(step: TrajectoryStep): TrajectoryStepSummary {
  const { request: _request, response: _response, ...summary } = step;
  return summary;
}

function matches(step: TrajectoryStep, query: TrajectoryQuery): boolean {
  const q = query.q?.toLowerCase();
  const text = `${step.name} ${step.target ?? ''} ${step.summary}`;
  const checks = [
    step.id > (query.after ?? 0),
    !query.kind || step.kind === query.kind,
    !query.actor || step.actor === query.actor,
    !query.stage || step.stage === query.stage,
    !query.outcome || step.outcome === query.outcome,
    !q || text.toLowerCase().includes(q),
  ];
  return checks.every(Boolean);
}

export function fixturePage(
  steps: readonly TrajectoryStep[],
  query: TrajectoryQuery,
): TrajectoryPage {
  const settled = steps.slice(0, Math.max(steps.length - STREAMED_TAIL, 0));
  const total = settled.filter((step) =>
    matches(step, { ...query, after: 0 }),
  ).length;
  const hits = settled.filter((step) => matches(step, query));
  const limit = query.limit ?? 100;
  const page = hits.slice(0, limit).map(summaryOf);
  const last = page[page.length - 1];
  return {
    steps: page,
    next_after: hits.length > limit && last ? last.id : null,
    total,
  };
}

function openVersion(step: TrajectoryStepSummary): TrajectoryStepSummary {
  return {
    ...step,
    status: 'RUNNING',
    ended_at: null,
    duration_ms: null,
    outcome: null,
    confidence: null,
    error: null,
  };
}

/** Replays the tail of the fixture: each step opens, then closes. */
export function fixtureStream(
  steps: readonly TrajectoryStep[],
  { onStep }: TrajectoryStreamHandlers,
): () => void {
  const tail = steps.slice(-STREAMED_TAIL).map(summaryOf);
  const timers = tail.flatMap((step, index) => {
    const at = (index + 1) * STREAM_GAP_MS;
    return [
      window.setTimeout(() => onStep(openVersion(step)), at),
      window.setTimeout(() => onStep(step), at + STREAM_GAP_MS * 0.6),
    ];
  });
  return () => timers.forEach((timer) => window.clearTimeout(timer));
}
