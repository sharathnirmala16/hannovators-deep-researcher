import type {
  TrajectoryKind,
  TrajectoryStatus,
  TrajectoryStepSummary,
  VerdictOutcome,
} from '@/domains/workspace';
import type { Tone } from '@/shared/ui/tag';

/** Step status tones (PLAN.md section 10.3): running info, error negative. */
export const STATUS_TONE: Record<TrajectoryStatus, Tone> = {
  RUNNING: 'info',
  OK: 'neutral',
  ERROR: 'negative',
  SKIPPED: 'neutral',
};

export const OUTCOME_TONE: Record<VerdictOutcome, Tone> = {
  KEPT: 'positive',
  REMOVED: 'negative',
  FLAGGED: 'caution',
};

export const OUTCOME_TEXT: Record<VerdictOutcome, string> = {
  KEPT: 'text-tone-positive',
  REMOVED: 'text-tone-negative',
  FLAGGED: 'text-tone-caution',
};

export const OUTCOME_FILL: Record<VerdictOutcome, string> = {
  KEPT: 'bg-tone-positive',
  REMOVED: 'bg-tone-negative',
  FLAGGED: 'bg-tone-caution',
};

/** Waterfall fill by kind family; model calls and decisions stand out. */
const KIND_FILL: Record<TrajectoryKind, string> = {
  STAGE: 'bg-shade-3',
  LLM: 'bg-tone-info',
  DECISION: 'bg-tone-null',
  SEARCH: 'bg-shade-5',
  FETCH: 'bg-shade-5',
  DOWNLOAD: 'bg-shade-5',
  EMBED: 'bg-shade-4',
  RETRIEVE: 'bg-shade-4',
  VERDICT: 'bg-shade-5',
  USER_ACTION: 'bg-shade-6',
  CHAT: 'bg-shade-6',
};

/** Fill of one waterfall bar: errors and running steps win over the kind. */
export function barFill(step: TrajectoryStepSummary): string {
  if (step.status === 'ERROR') return 'bg-tone-negative';
  if (step.status === 'RUNNING')
    return 'bg-tone-info motion-safe:animate-pulse';
  if (step.kind === 'VERDICT' && step.outcome) {
    return OUTCOME_FILL[step.outcome];
  }
  return KIND_FILL[step.kind];
}
