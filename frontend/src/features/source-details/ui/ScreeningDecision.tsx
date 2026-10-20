import type { SourceDetail } from '@/domains/workspace';
import { SectionHeader } from '@/shared/ui/section-header';

import { screeningFacts } from '../model/screeningFacts';
import { Facts } from './Facts';

/** Screening: score, z, votes against the threshold, and per-criterion votes. */
export function ScreeningDecision({
  detail,
  votesNeeded,
}: {
  detail: SourceDetail;
  /** The workspace's screening vote threshold T. */
  votesNeeded: number | null;
}) {
  const facts = screeningFacts(detail, votesNeeded);
  if (facts.length === 0) return null;
  return (
    <section aria-labelledby="source-screening" className="flex flex-col gap-2">
      <SectionHeader id="source-screening" title="Screening" />
      <Facts facts={facts} />
    </section>
  );
}
