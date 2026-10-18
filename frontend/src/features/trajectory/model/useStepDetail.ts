import { useEffect, useState } from 'react';

import type {
  TrajectoryStep,
  TrajectoryStepSummary,
} from '@/domains/workspace';

import type { TrajectorySource } from '../api/trajectorySource';
import { failureOf, type LoadPhase } from './trajectoryState';

export type StepDetail =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'ready'; step: TrajectoryStep }
  | Extract<LoadPhase, { phase: 'unavailable' | 'error' }>;

interface Loaded {
  key: string;
  detail: StepDetail;
}

/**
 * Fetches the full step (request and response bodies) for the open row, and
 * again when the row closes (RUNNING -> OK) on the live stream.
 */
export function useStepDetail(
  source: TrajectorySource | null,
  stepId: number | null,
  summary: TrajectoryStepSummary | undefined,
): StepDetail {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const key = detailKey(source, stepId, summary);

  useEffect(() => {
    if (!source || stepId === null) return undefined;
    const controller = new AbortController();
    source.step(stepId, controller.signal).then(
      (step) => setLoaded({ key, detail: { phase: 'ready', step } }),
      (error: unknown) => {
        if (controller.signal.aborted) return;
        const failure = failureOf(error);
        if (failure.phase === 'unavailable' || failure.phase === 'error') {
          setLoaded({ key, detail: failure });
        }
      },
    );
    return () => controller.abort();
  }, [source, stepId, key]);

  if (stepId === null) return { phase: 'idle' };
  return shownDetail(loaded, key, stepId);
}

/** Changes when the open row closes, so the bodies are fetched again. */
function detailKey(
  source: TrajectorySource | null,
  stepId: number | null,
  summary: TrajectoryStepSummary | undefined,
): string {
  const version = summary ? `${summary.status}:${summary.ended_at ?? ''}` : '';
  return `${source?.workspaceId ?? ''}:${stepId ?? ''}:${version}`;
}

function shownDetail(
  loaded: Loaded | null,
  key: string,
  stepId: number,
): StepDetail {
  if (loaded?.key === key) return loaded.detail;
  // Keep the older version of the same step on screen while it refreshes.
  const stale = loaded?.detail.phase === 'ready' ? loaded.detail : null;
  return stale?.step.id === stepId ? stale : { phase: 'loading' };
}
