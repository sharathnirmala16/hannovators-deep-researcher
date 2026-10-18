import type {
  StageId,
  TrajectoryActor,
  TrajectoryKind,
  TrajectoryQuery,
  TrajectoryStepSummary,
  VerdictOutcome,
} from '@/domains/workspace';

/** Toolbar state. Empty `kinds` means every kind. */
export interface TrajectoryFilters {
  q: string;
  kinds: readonly TrajectoryKind[];
  actor: TrajectoryActor | null;
  stage: StageId | null;
  outcome: VerdictOutcome | null;
  errorsOnly: boolean;
}

export const NO_FILTERS: TrajectoryFilters = {
  q: '',
  kinds: [],
  actor: null,
  stage: null,
  outcome: null,
  errorsOnly: false,
};

/** Page size for `GET .../trajectory` (the API caps it at 500). */
export const PAGE_SIZE = 300;

/**
 * Filters the API can apply. The API takes one kind, so several kind chips
 * (and "errors only") filter on the client instead.
 */
export function serverQuery(filters: TrajectoryFilters): TrajectoryQuery {
  const query: TrajectoryQuery = { limit: PAGE_SIZE };
  const q = filters.q.trim();
  const [onlyKind] = filters.kinds;
  if (q) query.q = q;
  if (onlyKind && filters.kinds.length === 1) query.kind = onlyKind;
  if (filters.actor) query.actor = filters.actor;
  if (filters.stage) query.stage = filters.stage;
  if (filters.outcome) query.outcome = filters.outcome;
  return query;
}

/** Filters the API cannot apply; used on every loaded row. */
export function matchesClientFilters(
  step: TrajectoryStepSummary,
  filters: TrajectoryFilters,
): boolean {
  if (filters.errorsOnly && step.status !== 'ERROR') return false;
  return filters.kinds.length === 0 || filters.kinds.includes(step.kind);
}

function matchesText(step: TrajectoryStepSummary, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  return [step.name, step.target ?? '', step.summary].some((text) =>
    text.toLowerCase().includes(needle),
  );
}

/**
 * The filters of `serverQuery`, applied on the client to rows that arrive on
 * the live stream (the API filtered every row it paged in).
 */
export function matchesServerFilters(
  step: TrajectoryStepSummary,
  filters: TrajectoryFilters,
): boolean {
  const [onlyKind] = filters.kinds;
  const checks = [
    filters.kinds.length !== 1 || step.kind === onlyKind,
    !filters.actor || step.actor === filters.actor,
    !filters.stage || step.stage === filters.stage,
    !filters.outcome || step.outcome === filters.outcome,
    matchesText(step, filters.q),
  ];
  return checks.every(Boolean);
}

export function hasFilters(filters: TrajectoryFilters): boolean {
  return (
    filters.q.trim() !== '' ||
    filters.kinds.length > 0 ||
    filters.actor !== null ||
    filters.stage !== null ||
    filters.outcome !== null ||
    filters.errorsOnly
  );
}

export function toggleKind(
  kinds: readonly TrajectoryKind[],
  kind: TrajectoryKind,
): TrajectoryKind[] {
  return kinds.includes(kind)
    ? kinds.filter((item) => item !== kind)
    : [...kinds, kind];
}
