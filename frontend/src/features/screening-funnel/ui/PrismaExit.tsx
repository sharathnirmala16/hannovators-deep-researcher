import { cn } from '@/shared/lib/cn';

interface PrismaExitProps {
  label: string;
  count: number;
}

/** Records leaving the flow: a branch off the main line to an exclusion box, as in PRISMA. */
export function PrismaExit({ label, count }: PrismaExitProps) {
  const removed = count > 0;
  return (
    <li className="relative flex min-w-0 items-center gap-0 py-1.5 pl-1">
      <span
        aria-hidden
        className="absolute top-0 bottom-0 left-1 w-px bg-shade-3"
      />
      <span aria-hidden className="h-px min-w-4 flex-1 bg-shade-3" />
      <span
        className={cn(
          'flex w-3/5 min-w-0 shrink-0 items-baseline justify-between gap-2 rounded-[3px] px-1.5 py-0.5 text-xs',
          removed
            ? 'bg-tone-negative-tint text-tone-negative'
            : 'bg-desk text-muted-foreground',
        )}
      >
        <span className="truncate" title={label}>
          {label}
        </span>
        <span className="shrink-0 font-semibold tabular-nums">{count}</span>
      </span>
    </li>
  );
}
