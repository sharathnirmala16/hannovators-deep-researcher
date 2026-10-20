import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { ToneDot } from '@/shared/ui/tag';

import { KindBadge } from './KindBadge';
import { STATUS_TONE } from './tones';

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
        'flex h-8 w-full min-w-0 items-center gap-2 rounded-md px-2 text-left text-sm transition-colors',
        current
          ? 'bg-accent font-medium shadow-[inset_2px_0_0_#18223a]'
          : 'hover:bg-desk',
      )}
    >
      <ToneDot
        tone={STATUS_TONE[step.status]}
        live={step.status === 'RUNNING'}
      />
      <span className="w-10 shrink-0 text-xs text-muted-foreground tabular-nums">
        {step.id}
      </span>
      <KindBadge kind={step.kind} className="w-24 shrink-0" />
      <span className="min-w-0 truncate">{step.name}</span>
    </button>
  );
}
