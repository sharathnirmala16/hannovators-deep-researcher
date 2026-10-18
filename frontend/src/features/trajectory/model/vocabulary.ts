import type {
  StageId,
  TrajectoryActor,
  TrajectoryKind,
  TrajectoryStatus,
  VerdictOutcome,
} from '@/domains/workspace';

/** Display order of the kind chips (PLAN.md section 5.3 recording rules). */
export const KINDS = [
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
] as const satisfies readonly TrajectoryKind[];

export const KIND_LABEL: Record<TrajectoryKind, string> = {
  STAGE: 'Stage',
  LLM: 'LLM',
  DECISION: 'Decision',
  SEARCH: 'Search',
  FETCH: 'Fetch',
  DOWNLOAD: 'Download',
  EMBED: 'Embed',
  RETRIEVE: 'Retrieve',
  VERDICT: 'Verdict',
  USER_ACTION: 'User action',
  CHAT: 'Chat',
};

/** Pipeline stages in run order. */
export const STAGES = [
  'ingest',
  'decompose',
  'search',
  'screen',
  'acquire',
  'appraise',
  'synthesize',
  'highlight',
  'compose',
] as const satisfies readonly StageId[];

export const STAGE_LABEL: Record<StageId, string> = {
  ingest: 'Ingest',
  decompose: 'Decompose',
  search: 'Search',
  screen: 'Screen',
  acquire: 'Acquire',
  appraise: 'Appraise',
  synthesize: 'Synthesize',
  highlight: 'Highlight',
  compose: 'Compose',
};

export const ACTORS = [
  'AGENT',
  'USER',
  'SYSTEM',
] as const satisfies readonly TrajectoryActor[];

export const ACTOR_LABEL: Record<TrajectoryActor, string> = {
  AGENT: 'Agent',
  USER: 'User',
  SYSTEM: 'System',
};

export const OUTCOMES = [
  'KEPT',
  'REMOVED',
  'FLAGGED',
] as const satisfies readonly VerdictOutcome[];

export const OUTCOME_LABEL: Record<VerdictOutcome, string> = {
  KEPT: 'Kept',
  REMOVED: 'Removed',
  FLAGGED: 'Flagged',
};

export const STATUS_LABEL: Record<TrajectoryStatus, string> = {
  RUNNING: 'Running',
  OK: 'OK',
  ERROR: 'Error',
  SKIPPED: 'Skipped',
};

const STAGE_SET: ReadonlySet<string> = new Set(STAGES);
const KIND_SET: ReadonlySet<string> = new Set(KINDS);
const ACTOR_SET: ReadonlySet<string> = new Set(ACTORS);
const OUTCOME_SET: ReadonlySet<string> = new Set(OUTCOMES);

export const isStage = (value: string): value is StageId =>
  STAGE_SET.has(value);
export const isKind = (value: string): value is TrajectoryKind =>
  KIND_SET.has(value);
export const isActor = (value: string): value is TrajectoryActor =>
  ACTOR_SET.has(value);
export const isOutcome = (value: string): value is VerdictOutcome =>
  OUTCOME_SET.has(value);
