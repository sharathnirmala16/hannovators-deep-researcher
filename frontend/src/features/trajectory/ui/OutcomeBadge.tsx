import type { VerdictOutcome } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { OUTCOME_LABEL } from '../model/vocabulary';
import { OUTCOME_TONE } from './statusStyles';

interface OutcomeBadgeProps {
  outcome: VerdictOutcome;
  className?: string | undefined;
}

export function OutcomeBadge({ outcome, className }: OutcomeBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm px-1.5 py-px text-xs font-medium',
        OUTCOME_TONE[outcome],
        className,
      )}
    >
      {OUTCOME_LABEL[outcome]}
    </span>
  );
}
