import { cn } from '@/shared/lib/cn';

import { formatPercent } from '../model/timing';

interface ProbabilityBarProps {
  option: string;
  probability: number;
  chosen: boolean;
}

/** One option of a decision: label, horizontal bar, and percentage. */
export function ProbabilityBar({
  option,
  probability,
  chosen,
}: ProbabilityBarProps) {
  const width = Math.min(Math.max(probability, 0), 1) * 100;
  return (
    <li className="grid grid-cols-[minmax(0,10rem)_1fr_3rem] items-center gap-3 text-xs">
      <span
        className={cn(
          'truncate',
          chosen ? 'font-semibold text-foreground' : 'text-muted-foreground',
        )}
        title={option}
      >
        {option}
      </span>
      <span className="h-1.5 overflow-hidden rounded-full bg-shade-2">
        <span
          className={cn(
            'block h-full rounded-full',
            chosen ? 'bg-tone-null' : 'bg-shade-4',
          )}
          style={{ width: `${width}%` }}
        />
      </span>
      <span
        className={cn(
          'text-right tabular-nums',
          chosen ? 'font-semibold text-foreground' : 'text-muted-foreground',
        )}
      >
        {formatPercent(probability)}
      </span>
    </li>
  );
}
