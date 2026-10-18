import type {
  TrajectoryPage,
  TrajectoryStepSummary,
} from '@/domains/workspace';

import { matchesServerFilters, type TrajectoryFilters } from './filters';
import { lastId, upsertSteps } from './steps';

type Step = TrajectoryStepSummary;

export type LoadPhase =
  | { phase: 'loading' }
  | { phase: 'ready' }
  /** The API answered 501: the endpoint is not built yet. */
  | { phase: 'unavailable'; message: string }
  | { phase: 'error'; message: string };

export interface TrajectoryState {
  /** Workspace + server query that `steps` belong to. */
  key: string | null;
  load: LoadPhase;
  steps: readonly Step[];
  /** Cursor of the next page, or null when every page is loaded. */
  nextAfter: number | null;
  total: number;
  loadingMore: boolean;
  moreError: string | null;
}

export const INITIAL_STATE: TrajectoryState = {
  key: null,
  load: { phase: 'loading' },
  steps: [],
  nextAfter: null,
  total: 0,
  loadingMore: false,
  moreError: null,
};

/** Every action names the key it was started for; stale ones are dropped. */
export type TrajectoryAction = { key: string } & (
  | { type: 'firstPage'; page: TrajectoryPage }
  | { type: 'failed'; load: LoadPhase }
  | { type: 'loadingMore' }
  | { type: 'morePage'; page: TrajectoryPage }
  | { type: 'moreFailed'; message: string }
  | { type: 'caughtUp'; page: TrajectoryPage }
  | { type: 'streamed'; steps: readonly Step[]; filters: TrajectoryFilters }
);

function onStreamed(
  state: TrajectoryState,
  incoming: readonly Step[],
  filters: TrajectoryFilters,
): TrajectoryState {
  const known = new Set(state.steps.map((step) => step.id));
  const newest = lastId(state.steps);
  const accepted = incoming.filter(
    (step) =>
      known.has(step.id) ||
      (matchesServerFilters(step, filters) &&
        (state.nextAfter === null || step.id <= newest)),
  );
  if (accepted.length === 0) return state;
  const steps = upsertSteps(state.steps, accepted);
  return {
    ...state,
    steps,
    total: state.total + (steps.length - state.steps.length),
  };
}

function withPage(
  state: TrajectoryState,
  page: TrajectoryPage,
): TrajectoryState {
  const steps = upsertSteps(state.steps, page.steps);
  return {
    ...state,
    steps,
    nextAfter: page.next_after,
    total: Math.max(page.total, steps.length),
    loadingMore: false,
    moreError: null,
  };
}

/** Steps missed while live updates were paused. */
function onCaughtUp(
  state: TrajectoryState,
  page: TrajectoryPage,
): TrajectoryState {
  const merged = withPage(state, page);
  return {
    ...merged,
    nextAfter: state.nextAfter ?? page.next_after,
    total: state.total + (merged.steps.length - state.steps.length),
  };
}

export function trajectoryReducer(
  state: TrajectoryState,
  action: TrajectoryAction,
): TrajectoryState {
  if (action.type === 'firstPage') {
    const fresh = { ...INITIAL_STATE, key: action.key };
    return { ...withPage(fresh, action.page), load: { phase: 'ready' } };
  }
  if (action.type === 'failed') {
    return { ...INITIAL_STATE, key: action.key, load: action.load };
  }
  if (action.key !== state.key) return state;
  switch (action.type) {
    case 'loadingMore':
      return { ...state, loadingMore: true, moreError: null };
    case 'morePage':
      return withPage(state, action.page);
    case 'moreFailed':
      return { ...state, loadingMore: false, moreError: action.message };
    case 'caughtUp':
      return onCaughtUp(state, action.page);
    case 'streamed':
      return onStreamed(state, action.steps, action.filters);
  }
}

/** 501 means "not built yet"; every other failure is an error. */
export function failureOf(error: unknown): LoadPhase {
  const message = error instanceof Error ? error.message : String(error);
  const status =
    typeof error === 'object' && error !== null && 'status' in error
      ? error.status
      : null;
  return status === 501
    ? { phase: 'unavailable', message }
    : { phase: 'error', message };
}
