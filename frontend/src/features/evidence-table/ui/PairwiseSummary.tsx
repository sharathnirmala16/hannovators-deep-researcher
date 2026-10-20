import { useId } from 'react';

import type { Synthesis } from '@/domains/workspace';
import { plainMath } from '@/shared/lib/plainMath';

import { CertaintyBadge } from './CertaintyBadge';
import type { CitationIndex } from './citations';
import { CitedText } from './CitedText';
import { GradeDomains } from './GradeDomains';
import { SourceCitation } from './SourceCitation';

type Summary = Synthesis['pairwise_summaries'][number];

/** One comparison: outcome, certainty, the summary, GRADE, and its studies. */
export function PairwiseSummary({
  summary,
  citations,
}: {
  summary: Summary;
  citations: CitationIndex;
}) {
  const titleId = useId();
  const studies = summary.source_ids
    .map((id) => citations.byId.get(id))
    .filter((source) => source !== undefined);
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-2">
      <header className="flex flex-col gap-0.5">
        <div className="flex items-start gap-3">
          <h4
            id={titleId}
            className="reading min-w-0 flex-1 text-base font-semibold text-foreground"
          >
            {plainMath(summary.outcome)}
          </h4>
          <CertaintyBadge certainty={summary.grade.certainty} />
        </div>
        <p className="text-xs text-muted-foreground">
          {plainMath(summary.intervention)} vs {plainMath(summary.comparison)}
        </p>
      </header>
      <p className="reading max-w-[72ch] text-sm leading-[22px] text-foreground">
        <CitedText text={summary.summary} citations={citations} />
      </p>
      <GradeDomains grade={summary.grade} />
      {studies.length > 0 ? (
        <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>Studies</span>
          {studies.map((source) => (
            <span key={source.id} className="text-foreground">
              <SourceCitation source={source} />
            </span>
          ))}
        </p>
      ) : null}
    </section>
  );
}
