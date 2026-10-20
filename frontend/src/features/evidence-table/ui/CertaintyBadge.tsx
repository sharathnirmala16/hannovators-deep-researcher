import { CERTAINTY_TONE, type GradeCertainty } from '@/domains/workspace';
import { Tag, type Tone } from '@/shared/ui/tag';

import { CERTAINTY_LABEL, CERTAINTY_LEVEL } from '../model/evidence';

const STRONG: Record<Tone, string> = {
  positive: 'text-tone-positive',
  negative: 'text-tone-negative',
  caution: 'text-tone-caution',
  info: 'text-tone-info',
  null: 'text-tone-null',
  neutral: 'text-tone-neutral',
};

/** GRADE certainty in its native notation (⊕⊕⊕◯), then the label. */
export function CertaintyBadge({ certainty }: { certainty: GradeCertainty }) {
  const level = CERTAINTY_LEVEL[certainty];
  const label = CERTAINTY_LABEL[certainty];
  const tone = CERTAINTY_TONE[certainty];
  return (
    <span
      role="img"
      aria-label={`GRADE certainty ${label.toLowerCase()}, ${level} of 4`}
      className="inline-flex shrink-0 items-center gap-1.5"
    >
      <span
        aria-hidden
        className={`text-sm leading-none tracking-[0.08em] ${STRONG[tone]}`}
      >
        {'⊕'.repeat(level)}
        {'◯'.repeat(4 - level)}
      </span>
      <Tag tone={tone} aria-hidden>
        {label}
      </Tag>
    </span>
  );
}
