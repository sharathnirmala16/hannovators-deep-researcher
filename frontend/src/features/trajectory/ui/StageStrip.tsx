import type { StageId } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import type { StageSummary } from '../model/stageSummary';
import { laneClass } from './laneClass';
import { OutcomeTally } from './OutcomeTally';
import { StageLane } from './StageLane';

interface StageStripProps {
  summary: StageSummary;
  active: StageId | null;
  onSelect: (stage: StageId | null) => void;
}

/**
 * Swimlane summary: one lane per stage in run order, sized by its step count,
 * with its keep / remove split. Clicking a lane filters the table to it.
 */
export function StageStrip({ summary, active, onSelect }: StageStripProps) {
  if (summary.lanes.length === 0) return null;
  return (
    <div role="group" aria-label="Stages" className="flex items-stretch gap-1">
      <button
        type="button"
        aria-pressed={active === null}
        onClick={() => onSelect(null)}
        className={cn(laneClass(active === null), 'w-32 shrink-0')}
      >
        <span className="text-sm font-medium">All stages</span>
        <OutcomeTally outcomes={summary.outcomes} />
      </button>
      {summary.lanes.map((lane) => (
        <StageLane
          key={lane.stage}
          lane={lane}
          pressed={active === lane.stage}
          onToggle={() => onSelect(active === lane.stage ? null : lane.stage)}
        />
      ))}
    </div>
  );
}
