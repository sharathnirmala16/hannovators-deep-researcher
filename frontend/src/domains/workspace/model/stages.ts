import {
  stageIdSchema,
  type StageId,
  type WorkspaceStatus,
} from '../api/enums';
import type { TraceEvent } from '../api/schema';

/** The nine pipeline stages in run order. */
export const STAGES: readonly StageId[] = stageIdSchema.options;

export const STAGE_LABEL: Record<StageId, string> = {
  ingest: 'Read seeds',
  decompose: 'Decompose',
  search: 'Search',
  screen: 'Screen',
  acquire: 'Get full text',
  appraise: 'Appraise',
  synthesize: 'Synthesize',
  highlight: 'Highlight',
  compose: 'Compose',
};

export type StageState = 'done' | 'active' | 'review' | 'failed' | 'pending';

interface RunPosition {
  status: WorkspaceStatus;
  current_stage: StageId | null;
}

function eventStages(events: readonly TraceEvent[]) {
  const completed = new Set<StageId>();
  const failed = new Set<StageId>();
  let latest: StageId | null = null;
  for (const event of events) {
    if (event.kind === 'STAGE_COMPLETED') completed.add(event.stage);
    if (event.kind === 'STAGE_FAILED') failed.add(event.stage);
    if (event.kind === 'STAGE_STARTED') latest = event.stage;
  }
  return { completed, failed, latest };
}

const CURRENT_STATE: Record<WorkspaceStatus, StageState> = {
  CREATED: 'pending',
  RUNNING: 'active',
  AWAITING_REVIEW: 'review',
  COMPLETED: 'done',
  FAILED: 'failed',
};

/** Where each stage stands, from the workspace position and its events. */
export function stageStates(
  position: RunPosition,
  events: readonly TraceEvent[],
): Record<StageId, StageState> {
  const { completed, failed, latest } = eventStages(events);
  const current = position.current_stage ?? latest;
  const currentIndex = current ? STAGES.indexOf(current) : -1;
  const allDone = position.status === 'COMPLETED';
  const entries = STAGES.map((stage, index): [StageId, StageState] => {
    if (failed.has(stage)) return [stage, 'failed'];
    if (allDone) return [stage, 'done'];
    if (index === currentIndex) return [stage, CURRENT_STATE[position.status]];
    if (completed.has(stage) || index < currentIndex) return [stage, 'done'];
    return [stage, 'pending'];
  });
  return Object.fromEntries(entries) as Record<StageId, StageState>;
}

export interface StageActivity {
  stage: StageId;
  startedAt: string | null;
  endedAt: string | null;
  /** The newest message of the stage. */
  message: string | null;
  eventCount: number;
  warnings: number;
}

/** Per-stage start, end, and newest message, in run order. */
export function stageActivity(events: readonly TraceEvent[]): StageActivity[] {
  const byStage = new Map<StageId, StageActivity>();
  for (const event of events) {
    const item = byStage.get(event.stage) ?? {
      stage: event.stage,
      startedAt: null,
      endedAt: null,
      message: null,
      eventCount: 0,
      warnings: 0,
    };
    item.eventCount += 1;
    item.message = event.message;
    if (event.kind === 'STAGE_STARTED') item.startedAt ??= event.created_at;
    if (event.kind === 'STAGE_COMPLETED' || event.kind === 'STAGE_FAILED') {
      item.endedAt = event.created_at;
    }
    if (event.kind === 'WARNING') item.warnings += 1;
    byStage.set(event.stage, item);
  }
  return STAGES.flatMap((stage) => {
    const item = byStage.get(stage);
    return item ? [item] : [];
  });
}
