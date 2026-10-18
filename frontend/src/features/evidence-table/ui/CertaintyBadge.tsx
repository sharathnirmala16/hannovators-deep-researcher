import { CERTAINTY_TONE, type GradeCertainty } from '@/domains/workspace';
import { Tag } from '@/shared/ui/tag';

import { CERTAINTY_LABEL, CERTAINTY_LEVEL } from '../model/evidence';

/** GRADE certainty in its native notation: filled circles out of four. */
export function CertaintyBadge({ certainty }: { certainty: GradeCertainty }) {
  const level = CERTAINTY_LEVEL[certainty];
  const label = CERTAINTY_LABEL[certainty];
  return (
    <Tag
      tone={CERTAINTY_TONE[certainty]}
      aria-label={`Certainty ${label}, ${level} of 4`}
    >
      <span aria-hidden className="tracking-[0.1em]">
        {'⊕'.repeat(level)}
        {'◯'.repeat(4 - level)}
      </span>
      {label}
    </Tag>
  );
}
