import type { TrajectoryStepSummary } from '@/domains/workspace';

/** What the detail tabs need from the table: loaded rows and navigation. */
export interface StepContext {
  steps: readonly TrajectoryStepSummary[];
  byId: ReadonlyMap<number, TrajectoryStepSummary>;
  origin: number;
  sourceTitle: (sourceId: string) => string | null;
  onOpenStep: (id: number) => void;
  onOpenSource: (sourceId: string, step: TrajectoryStepSummary) => void;
}
