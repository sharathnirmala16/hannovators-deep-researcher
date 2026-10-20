import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { barFor, type TimeRange } from '../model/timing';
import { barFill } from './tones';

interface WaterfallBarProps {
  step: TrajectoryStepSummary;
  range: TimeRange;
}

/** Start and duration relative to the visible rows, like a network waterfall. */
export function WaterfallBar({ step, range }: WaterfallBarProps) {
  const bar = barFor(step, range);
  return (
    <span
      aria-hidden
      className="relative block h-1.5 w-full rounded-full bg-shade-1"
    >
      <span
        className={cn(
          'absolute inset-y-0 min-w-1.5 rounded-full',
          barFill(step),
        )}
        style={{ left: `${bar.left}%`, width: `${bar.width}%` }}
      />
    </span>
  );
}
