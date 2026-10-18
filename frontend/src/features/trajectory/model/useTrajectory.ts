import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from 'react';

import type { TrajectoryStepSummary } from '@/domains/workspace';

import type { TrajectorySource } from '../api/trajectorySource';
import { NO_FILTERS, serverQuery, type TrajectoryFilters } from './filters';
import { resumeCursor } from './steps';
import {
  INITIAL_STATE,
  failureOf,
  trajectoryReducer,
  type LoadPhase,
  type TrajectoryState,
} from './trajectoryState';

export type LiveStatus = 'off' | 'connecting' | 'live' | 'interrupted';

/** Stream events are applied in batches, so a burst renders once. */
const FLUSH_MS = 120;
const CATCH_UP_LIMIT = 500;

interface UseTrajectoryOptions {
  source: TrajectorySource | null;
  /** Filters with the debounced text query. */
  filters: TrajectoryFilters;
  live: boolean;
}

export interface TrajectoryData extends Omit<TrajectoryState, 'key' | 'load'> {
  load: LoadPhase;
  liveStatus: LiveStatus;
  loadMore: () => void;
  /** Load the first page again after a failure. */
  retry: () => void;
}

function useServerQuery(filters: TrajectoryFilters) {
  const { q, actor, stage, outcome, kinds } = filters;
  const onlyKind = kinds.length === 1 ? (kinds[0] ?? null) : null;
  return useMemo(
    () =>
      serverQuery({
        ...NO_FILTERS,
        q,
        actor,
        stage,
        outcome,
        kinds: onlyKind ? [onlyKind] : [],
      }),
    [q, actor, stage, outcome, onlyKind],
  );
}

/** Pages the trajectory (cursor `after`) and merges the live stream. */
export function useTrajectory({
  source,
  filters,
  live,
}: UseTrajectoryOptions): TrajectoryData {
  const [state, dispatch] = useReducer(trajectoryReducer, INITIAL_STATE);
  const query = useServerQuery(filters);
  const [attempt, setAttempt] = useState(0);
  const key = `${source?.workspaceId ?? ''}|${attempt}|${JSON.stringify(query)}`;
  const current = state.key === key ? state : { ...INITIAL_STATE, key };
  const ready = current.load.phase === 'ready';
  const latest = useRef({ filters, state: current });
  useEffect(() => {
    latest.current = { filters, state: current };
  });

  useEffect(() => {
    if (!source) return undefined;
    const controller = new AbortController();
    source.list(query, controller.signal).then(
      (page) => dispatch({ key, type: 'firstPage', page }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          dispatch({ key, type: 'failed', load: failureOf(error) });
        }
      },
    );
    return () => controller.abort();
  }, [source, query, key]);

  const liveStatus = useLiveStream({
    source,
    key,
    live,
    ready,
    dispatch,
    latest,
  });
  useCatchUp({ source, key, query, live, ready, dispatch, latest });

  const { nextAfter, loadingMore } = current;
  const loadMore = useCallback(() => {
    if (!source || nextAfter === null || loadingMore) return;
    dispatch({ key, type: 'loadingMore' });
    source
      .list({ ...query, after: nextAfter }, new AbortController().signal)
      .then(
        (page) => dispatch({ key, type: 'morePage', page }),
        (error: unknown) =>
          dispatch({ key, type: 'moreFailed', message: String(error) }),
      );
  }, [source, query, key, nextAfter, loadingMore]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  return {
    load: source ? current.load : { phase: 'loading' },
    steps: current.steps,
    nextAfter: current.nextAfter,
    total: current.total,
    loadingMore: current.loadingMore,
    moreError: current.moreError,
    liveStatus: live ? liveStatus : 'off',
    loadMore,
    retry,
  };
}

interface StreamOptions {
  source: TrajectorySource | null;
  key: string;
  live: boolean;
  ready: boolean;
  dispatch: (action: Parameters<typeof trajectoryReducer>[1]) => void;
  latest: { current: { filters: TrajectoryFilters; state: TrajectoryState } };
}

function useLiveStream({
  source,
  key,
  live,
  ready,
  dispatch,
  latest,
}: StreamOptions): LiveStatus {
  const [status, setStatus] = useState<{ key: string; live: boolean } | null>(
    null,
  );
  useEffect(() => {
    if (!source || !live || !ready) return undefined;
    const buffer: TrajectoryStepSummary[] = [];
    let timer: number | null = null;
    const flush = () => {
      timer = null;
      const steps = buffer.splice(0);
      dispatch({
        key,
        type: 'streamed',
        steps,
        filters: latest.current.filters,
      });
    };
    const close = source.subscribe({
      onStep: (step) => {
        buffer.push(step);
        setStatus({ key, live: true });
        timer ??= window.setTimeout(flush, FLUSH_MS);
      },
      onError: () => setStatus({ key, live: false }),
    });
    return () => {
      close();
      if (timer !== null) window.clearTimeout(timer);
      setStatus(null);
    };
  }, [source, key, live, ready, dispatch, latest]);
  if (!status || status.key !== key) return 'connecting';
  return status.live ? 'live' : 'interrupted';
}

interface CatchUpOptions extends StreamOptions {
  query: ReturnType<typeof serverQuery>;
}

/** After a pause, fetch the steps that were missed, then the stream resumes. */
function useCatchUp({
  source,
  key,
  query,
  live,
  ready,
  dispatch,
  latest,
}: CatchUpOptions) {
  const wasLive = useRef(live);
  useEffect(() => {
    const resumed = live && !wasLive.current;
    wasLive.current = live;
    if (!resumed || !source || !ready) return undefined;
    const controller = new AbortController();
    const after = resumeCursor(latest.current.state.steps);
    source
      .list({ ...query, after, limit: CATCH_UP_LIMIT }, controller.signal)
      .then(
        (page) => dispatch({ key, type: 'caughtUp', page }),
        () => undefined,
      );
    return () => controller.abort();
  }, [source, key, query, live, ready, dispatch, latest]);
}
