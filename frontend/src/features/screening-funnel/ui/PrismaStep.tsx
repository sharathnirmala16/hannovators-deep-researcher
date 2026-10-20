import { cn } from '@/shared/lib/cn';

interface PrismaStepProps {
  label: string;
  count: number;
  /** Records removed on the way into this step (drawn after the kept part). */
  removed: number;
  /** The first step's count: the full bar width. */
  max: number;
  /** Kept records are positive; the first step (all records) is neutral. */
  kept: boolean;
}

const share = (value: number, max: number) =>
  max > 0 ? `${Math.min(100, (value / max) * 100)}%` : '0%';

/** One box of the flow: label, count, and a bar proportional to the records found. */
export function PrismaStep({
  label,
  count,
  removed,
  max,
  kept,
}: PrismaStepProps) {
  return (
    <li className="flex min-w-0 flex-col gap-1">
      <div className="flex min-w-0 items-baseline gap-2">
        <span className="truncate text-sm text-foreground" title={label}>
          {label}
        </span>
        <span
          className={cn(
            'ml-auto shrink-0 text-sm font-semibold tabular-nums',
            kept ? 'text-tone-positive' : 'text-foreground',
          )}
        >
          {count}
        </span>
      </div>
      <span
        aria-hidden
        className="flex h-2 w-full overflow-hidden rounded-[3px] bg-shade-1"
      >
        <span
          className={cn(
            'h-full',
            kept ? 'bg-tone-positive' : 'bg-tone-neutral',
            count > 0 && 'min-w-0.5',
          )}
          style={{ width: share(count, max) }}
        />
        {removed > 0 ? (
          <span
            className="h-full bg-tone-negative-tint"
            style={{ width: share(removed, max) }}
          />
        ) : null}
      </span>
    </li>
  );
}
