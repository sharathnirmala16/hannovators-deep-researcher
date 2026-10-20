import { useCallback, useMemo, useState } from 'react';

import type { TrajectoryStepSummary } from '@/domains/workspace';

import type { TrajectorySource } from '../api/trajectorySource';
import {
  NO_FILTERS,
  matchesClientFilters,
  type TrajectoryFilters,
} from './filters';
import { countKinds, summarizeStages } from './stageSummary';
import { indexById } from './steps';
import { timeRange } from './timing';
import { useDebouncedValue, useSettledEffect } from './useDebounced';
import { useStepDetail } from './useStepDetail';
import { useTrajectory } from './useTrajectory';

const QUERY_DEBOUNCE_MS = 250;
/** Audit settled actions only, not every keystroke or arrow press. */
const AUDIT_DEBOUNCE_MS = 800;

function filterAction(filters: TrajectoryFilters) {
  return {
    name: 'user.trajectory.filter',
    summary: 'Changed the trajectory filters.',
    details: {
      q: filters.q.trim(),
      kinds: [...filters.kinds],
      actor: filters.actor,
      stage: filters.stage,
      outcome: filters.outcome,
      errors_only: filters.errorsOnly,
    },
  };
}

function openAction(id: number, step: TrajectoryStepSummary | undefined) {
  return {
    name: 'user.trajectory.open_step',
    summary: `Opened trajectory step #${id}${step ? ` ${step.name}` : ''}.`,
    target: step?.target ?? null,
    source_ids: step ? [...step.source_ids] : [],
    details: { step_id: id, kind: step?.kind ?? null },
  };
}

/** State and derived data of the trajectory view for one workspace. */
export function useTrajectoryController(
  source: TrajectorySource | null,
  step: number | null = null,
) {
  const [filters, setFilters] = useState<TrajectoryFilters>(NO_FILTERS);
  const [live, setLive] = useState(true);
  const [cursorId, setCursorId] = useState<number | null>(null);
  const [openId, setOpenId] = useState<number | null>(step);
  const [seenStep, setSeenStep] = useState(step);
  // A deep link (`?step=<id>` from the Research tab) opens that step.
  if (seenStep !== step) {
    setSeenStep(step);
    if (step !== null) {
      setOpenId(step);
      setCursorId(step);
    }
  }
  const q = useDebouncedValue(filters.q, QUERY_DEBOUNCE_MS);
  const queryFilters = useMemo(() => ({ ...filters, q }), [filters, q]);
  const data = useTrajectory({ source, filters: queryFilters, live });

  const { kinds, errorsOnly } = filters;
  const rows = useMemo(
    () =>
      data.steps.filter((step) =>
        matchesClientFilters(step, { ...NO_FILTERS, kinds, errorsOnly }),
      ),
    [data.steps, kinds, errorsOnly],
  );
  const byId = useMemo(() => indexById(data.steps), [data.steps]);
  const range = useMemo(() => timeRange(rows), [rows]);
  const origin = useMemo(() => timeRange(data.steps)?.start ?? 0, [data.steps]);
  const stages = useMemo(() => summarizeStages(data.steps), [data.steps]);
  const kindCounts = useMemo(() => countKinds(data.steps), [data.steps]);
  const openSummary = openId === null ? undefined : byId.get(openId);
  const detail = useStepDetail(source, openId, openSummary);

  useSettledEffect(filters, AUDIT_DEBOUNCE_MS, (settled) =>
    source?.record(filterAction(settled)),
  );
  useSettledEffect(openId, AUDIT_DEBOUNCE_MS, (id) => {
    if (id !== null) source?.record(openAction(id, byId.get(id)));
  });

  const open = useCallback((id: number) => {
    setCursorId(id);
    setOpenId(id);
  }, []);
  const moveCursor = useCallback((id: number, follow: boolean) => {
    setCursorId(id);
    if (follow) setOpenId(id);
  }, []);
  const close = useCallback(() => setOpenId(null), []);

  return {
    filters,
    setFilters,
    live,
    setLive,
    data,
    rows,
    byId,
    range,
    origin,
    stages,
    kindCounts,
    cursorId,
    openId,
    openSummary,
    detail,
    open,
    moveCursor,
    close,
  };
}
