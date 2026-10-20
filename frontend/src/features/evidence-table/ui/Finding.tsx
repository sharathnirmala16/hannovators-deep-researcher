import type { ClaimView, HighlightView } from '@/domains/workspace';
import { Tag } from '@/shared/ui/tag';

import { VERDICT } from '../model/evidence';
import { ClaimCell } from './ClaimCell';
import { humanize } from './findings';

/** One extracted result: its label, then the value or sentence to trace. */
export function Finding({
  claim,
  highlights,
}: {
  claim: ClaimView;
  highlights: readonly HighlightView[];
}) {
  const verdict = claim.verdict === 'SUPPORTED' ? null : VERDICT[claim.verdict];
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">
          {humanize(claim.label)}
        </span>
        {verdict ? <Tag tone={verdict.tone}>{verdict.label}</Tag> : null}
      </div>
      <ClaimCell
        claim={claim}
        highlights={highlights}
        className="reading max-w-[72ch] text-sm leading-[22px] text-foreground"
      />
    </div>
  );
}
