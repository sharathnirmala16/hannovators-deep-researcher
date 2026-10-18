import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { KindBadge } from './KindBadge';
import { STATUS_DOT, FOCUS_RING } from './statusStyles';

interface StepLinkProps {
  step: TrajectoryStepSummary;
  onOpen: (id: number) => void;
  current?: boolean;
}

/** A compact step reference that opens the step in the detail panel. */
export function StepLink({ step, onOpen, current = false }: StepLinkProps) {
  return (
    <button
      type="button"
      aria-current={current || undefined}
      onClick={() => onOpen(step.id)}
      className={cn(
        'flex h-7 w-full min-w-0 items-center gap-2 rounded-md px-2 text-left text-xs hover:bg-muted',
        current && 'bg-muted font-medium',
        FOCUS_RING,
      )}
    >
      <span
        aria-hidden
        className={cn(
          'size-1.5 shrink-0 rounded-full',
          STATUS_DOT[step.status],
        )}
      />
      <span className="w-10 shrink-0 text-muted-foreground tabular-nums">
        #{step.id}
      </span>
      <KindBadge kind={step.kind} className="w-24 shrink-0" />
      <span className="min-w-0 truncate">{step.name}</span>
    </button>
  );
}
