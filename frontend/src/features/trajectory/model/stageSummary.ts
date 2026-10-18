import type {
  StageId,
  TrajectoryKind,
  TrajectoryStepSummary,
  VerdictOutcome,
} from '@/domains/workspace';

import { KINDS, STAGES } from './vocabulary';

type Step = TrajectoryStepSummary;

export type OutcomeCounts = Record<VerdictOutcome, number>;

export interface StageLane {
  stage: StageId;
  count: number;
  errors: number;
  /** Kinds in chip order with their counts, zero counts left out. */
  kinds: readonly (readonly [TrajectoryKind, number])[];
  outcomes: OutcomeCounts;
  /** Wall time between the first start and the last end, in ms. */
  spanMs: number;
}

export interface StageSummary {
  lanes: readonly StageLane[];
  outcomes: OutcomeCounts;
}

const noOutcomes = (): OutcomeCounts => ({ KEPT: 0, REMOVED: 0, FLAGGED: 0 });

function laneOf(stage: StageId, steps: readonly Step[]): StageLane {
  const kinds = new Map<TrajectoryKind, number>();
  const outcomes = noOutcomes();
  let errors = 0;
  let start = Infinity;
  let end = -Infinity;
  for (const step of steps) {
    kinds.set(step.kind, (kinds.get(step.kind) ?? 0) + 1);
    if (step.outcome) outcomes[step.outcome] += 1;
    if (step.status === 'ERROR') errors += 1;
    const begin = Date.parse(step.started_at);
    start = Math.min(start, begin);
    end = Math.max(end, begin + (step.duration_ms ?? 0));
  }
  return {
    stage,
    count: steps.length,
    errors,
    kinds: KINDS.flatMap((kind) => {
      const count = kinds.get(kind) ?? 0;
      return count > 0 ? [[kind, count] as const] : [];
    }),
    outcomes,
    spanMs: Number.isFinite(start) ? Math.max(end - start, 0) : 0,
  };
}

/** Counts per stage (run order) and kept / removed / flagged totals. */
export function summarizeStages(steps: readonly Step[]): StageSummary {
  const buckets = new Map<StageId, Step[]>();
  const outcomes = noOutcomes();
  for (const step of steps) {
    if (step.outcome) outcomes[step.outcome] += 1;
    if (!step.stage) continue;
    const bucket = buckets.get(step.stage) ?? [];
    bucket.push(step);
    buckets.set(step.stage, bucket);
  }
  const lanes = STAGES.flatMap((stage) => {
    const bucket = buckets.get(stage);
    return bucket ? [laneOf(stage, bucket)] : [];
  });
  return { lanes, outcomes };
}

export function countKinds(
  steps: readonly Step[],
): ReadonlyMap<TrajectoryKind, number> {
  const counts = new Map<TrajectoryKind, number>();
  for (const step of steps) {
    counts.set(step.kind, (counts.get(step.kind) ?? 0) + 1);
  }
  return counts;
}
