import type { VerdictOutcome } from '@/domains/workspace';
import { Tag } from '@/shared/ui/tag';

import { OUTCOME_LABEL } from '../model/vocabulary';
import { OUTCOME_TONE } from './tones';

/** Kept positive, removed negative, flagged caution. */
export function OutcomeTag({ outcome }: { outcome: VerdictOutcome }) {
  return <Tag tone={OUTCOME_TONE[outcome]}>{OUTCOME_LABEL[outcome]}</Tag>;
}
