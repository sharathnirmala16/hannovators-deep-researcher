import { cn } from '@/shared/lib/cn';

import type { OutcomeCounts } from '../model/stageSummary';
import { formatCount } from '../model/timing';
import { OUTCOMES } from '../model/vocabulary';
import { OUTCOME_TEXT } from './statusStyles';

const WORD = { KEPT: 'kept', REMOVED: 'removed', FLAGGED: 'flagged' } as const;
const SEGMENT = {
  KEPT: 'bg-emerald-500',
  REMOVED: 'bg-rose-500',
  FLAGGED: 'bg-amber-500',
} as const;

interface OutcomeTallyProps {
  outcomes: OutcomeCounts;
  errors?: number;
}

/** Verdict counts as words plus a thin split bar; quiet when there are none. */
export function OutcomeTally({ outcomes, errors = 0 }: OutcomeTallyProps) {
  const verdicts = outcomes.KEPT + outcomes.REMOVED + outcomes.FLAGGED;
  const present = OUTCOMES.filter((outcome) => outcomes[outcome] > 0);
  return (
    <span className="flex w-full flex-col gap-1">
      <span className="flex flex-wrap gap-x-2 text-xs tabular-nums">
        {present.map((outcome) => (
          <span key={outcome} className={OUTCOME_TEXT[outcome]}>
            {formatCount(outcomes[outcome])} {WORD[outcome]}
          </span>
        ))}
        {errors > 0 ? (
          <span className="text-rose-600 dark:text-rose-400">
            {formatCount(errors)} {errors === 1 ? 'error' : 'errors'}
          </span>
        ) : null}
        {present.length === 0 && errors === 0 ? (
          <span className="text-muted-foreground">No verdicts</span>
        ) : null}
      </span>
      <span
        aria-hidden
        className="flex h-1 w-full overflow-hidden rounded-full bg-foreground/10"
      >
        {verdicts > 0
          ? present.map((outcome) => (
              <span
                key={outcome}
                className={cn('h-full', SEGMENT[outcome])}
                style={{ width: `${(outcomes[outcome] / verdicts) * 100}%` }}
              />
            ))
          : null}
      </span>
    </span>
  );
}
