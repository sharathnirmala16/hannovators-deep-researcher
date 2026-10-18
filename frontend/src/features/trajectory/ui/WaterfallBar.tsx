import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { barFor, type TimeRange } from '../model/timing';
import { BAR_COLOR } from './statusStyles';

interface WaterfallBarProps {
  step: TrajectoryStepSummary;
  range: TimeRange;
}

/** Start and duration relative to the visible rows, like a network waterfall. */
export function WaterfallBar({ step, range }: WaterfallBarProps) {
  const bar = barFor(step, range);
  return (
    <span aria-hidden className="relative block h-2.5 w-full">
      <span
        className={cn(
          'absolute inset-y-0 min-w-0.5 rounded-[2px]',
          BAR_COLOR[step.status],
          bar.open && 'opacity-70',
        )}
        style={{ left: `${bar.left}%`, width: `${bar.width}%` }}
      />
    </span>
  );
}
