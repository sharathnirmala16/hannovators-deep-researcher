import type { StageId } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip';

import type { StageLane, StageSummary } from '../model/stageSummary';
import { formatCount, formatDuration } from '../model/timing';
import { KIND_LABEL, STAGE_LABEL } from '../model/vocabulary';
import { OutcomeTally } from './OutcomeTally';
import { FOCUS_RING } from './statusStyles';

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
    <div
      role="group"
      aria-label="Stages"
      className="flex items-stretch gap-1 border-b px-3 py-2"
    >
      <button
        type="button"
        aria-pressed={active === null}
        onClick={() => onSelect(null)}
        className={cn(laneClass(active === null), 'w-32 shrink-0')}
      >
        <span className="text-[13px] font-medium">All stages</span>
        <OutcomeTally outcomes={summary.outcomes} />
      </button>
      {summary.lanes.map((lane) => (
        <Lane
          key={lane.stage}
          lane={lane}
          pressed={active === lane.stage}
          onToggle={() => onSelect(active === lane.stage ? null : lane.stage)}
        />
      ))}
    </div>
  );
}

interface LaneProps {
  lane: StageLane;
  pressed: boolean;
  onToggle: () => void;
}

function Lane({ lane, pressed, onToggle }: LaneProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-pressed={pressed}
          onClick={onToggle}
          style={{ flexGrow: Math.max(1, Math.sqrt(lane.count)) }}
          className={cn(laneClass(pressed), 'min-w-24 basis-0')}
        >
          <span className="flex w-full items-baseline justify-between gap-2">
            <span className="truncate text-[13px] font-medium">
              {STAGE_LABEL[lane.stage]}
            </span>
            <span className="text-xs text-muted-foreground tabular-nums">
              {formatCount(lane.count)}
            </span>
          </span>
          <OutcomeTally outcomes={lane.outcomes} errors={lane.errors} />
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-64">
        <p className="font-medium">
          {STAGE_LABEL[lane.stage]}, {formatDuration(lane.spanMs)}
        </p>
        <ul className="mt-1 grid grid-cols-[1fr_auto] gap-x-4 tabular-nums">
          {lane.kinds.map(([kind, count]) => (
            <li key={kind} className="contents">
              <span>{KIND_LABEL[kind]}</span>
              <span className="text-right">{formatCount(count)}</span>
            </li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}

function laneClass(pressed: boolean): string {
  return cn(
    'flex flex-col items-start justify-between gap-1 rounded-md px-2 py-1.5 text-left transition-colors',
    pressed
      ? 'bg-muted ring-1 ring-foreground/40'
      : 'bg-muted/40 hover:bg-muted/70',
    FOCUS_RING,
  );
}
