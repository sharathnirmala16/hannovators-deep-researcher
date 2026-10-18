import type { GradeCertainty } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { CERTAINTY_LABEL, CERTAINTY_LEVEL } from '../model/evidence';

const TONE: Record<GradeCertainty, string> = {
  HIGH: 'border-emerald-700/30 bg-emerald-50 text-emerald-900',
  MODERATE: 'border-sky-700/30 bg-sky-50 text-sky-900',
  LOW: 'border-amber-700/30 bg-amber-50 text-amber-900',
  VERY_LOW: 'border-rose-700/30 bg-rose-50 text-rose-900',
};

/** GRADE certainty in its native notation: filled circles out of four. */
export function CertaintyBadge({ certainty }: { certainty: GradeCertainty }) {
  const level = CERTAINTY_LEVEL[certainty];
  const label = CERTAINTY_LABEL[certainty];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        TONE[certainty],
      )}
      aria-label={`Certainty ${label}, ${level} of 4`}
    >
      <span aria-hidden className="tracking-[0.15em]">
        {'⊕'.repeat(level)}
        {'◯'.repeat(4 - level)}
      </span>
      {label}
    </span>
  );
}
