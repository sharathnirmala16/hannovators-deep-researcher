import { useCallback, useMemo } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import { useWorkspace, type TrajectoryStepSummary } from '@/domains/workspace';

import type { TrajectorySource } from '../api/trajectorySource';
import type { StepContext } from './stepContext';

function useSourceTitles(): (sourceId: string) => string | null {
  const { load } = useWorkspace();
  const titles = useMemo(() => {
    const sources = load.status === 'ready' ? load.state.sources : [];
    return new Map(sources.map((item) => [item.id, item.title]));
  }, [load]);
  return useCallback((sourceId) => titles.get(sourceId) ?? null, [titles]);
}

interface StepContextOptions {
  source: TrajectorySource;
  steps: readonly TrajectoryStepSummary[];
  byId: ReadonlyMap<number, TrajectoryStepSummary>;
  origin: number;
  onOpenStep: (id: number) => void;
  /** Called after the source is selected, to switch to the Research tab. */
  onOpenSource?: ((sourceId: string) => void) | undefined;
}

/** What the detail tabs need: loaded rows, source titles, and navigation. */
export function useStepContext({
  source,
  steps,
  byId,
  origin,
  onOpenStep,
  onOpenSource,
}: StepContextOptions): StepContext {
  const { selectSource } = useEvidenceSelection();
  const sourceTitle = useSourceTitles();

  const openSource = useCallback(
    (sourceId: string, step: TrajectoryStepSummary) => {
      selectSource(sourceId);
      source.record({
        name: 'user.source.open',
        summary: `Opened ${sourceTitle(sourceId) ?? sourceId} from trajectory step #${step.id}.`,
        source_ids: [sourceId],
        details: { from: 'trajectory', step_id: step.id },
      });
      onOpenSource?.(sourceId);
    },
    [selectSource, source, sourceTitle, onOpenSource],
  );

  return useMemo(
    () => ({
      steps,
      byId,
      origin,
      sourceTitle,
      onOpenStep,
      onOpenSource: openSource,
    }),
    [steps, byId, origin, sourceTitle, onOpenStep, openSource],
  );
}
