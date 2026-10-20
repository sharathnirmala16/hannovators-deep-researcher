import { cn } from '@/shared/lib/cn';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip';

import type { StageLane as Lane } from '../model/stageSummary';
import { formatCount, formatDuration } from '../model/timing';
import { KIND_LABEL, STAGE_LABEL } from '../model/vocabulary';
import { laneClass } from './laneClass';
import { OutcomeTally } from './OutcomeTally';

interface StageLaneProps {
  lane: Lane;
  pressed: boolean;
  onToggle: () => void;
}

/** One stage: name, step count, verdict split; the tooltip lists its kinds. */
export function StageLane({ lane, pressed, onToggle }: StageLaneProps) {
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
            <span className="truncate text-sm font-medium">
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
