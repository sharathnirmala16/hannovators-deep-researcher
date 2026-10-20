import {
  isCounterEvidence,
  type Synthesis,
  type SourceView,
} from '@/domains/workspace';
import { plural } from '@/shared/lib/format';
import { plainMath } from '@/shared/lib/plainMath';

import { CertaintyBadge } from './CertaintyBadge';

type Summary = Synthesis['pairwise_summaries'][number];

interface OutcomeHeaderProps {
  summary: Summary;
  studies: readonly SourceView[];
  titleId: string;
}

/** Outcome in reading type, the comparison, study counts, and certainty. */
export function OutcomeHeader({
  summary,
  studies,
  titleId,
}: OutcomeHeaderProps) {
  const counter = studies.filter(isCounterEvidence).length;
  return (
    <header className="flex flex-col gap-1 px-4">
      <div className="flex items-start gap-3">
        <h3
          id={titleId}
          className="reading min-w-0 flex-1 text-base font-semibold text-foreground"
        >
          {plainMath(summary.outcome)}
        </h3>
        <CertaintyBadge certainty={summary.grade.certainty} />
      </div>
      <p className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
        <span>
          {plainMath(summary.intervention)} vs {plainMath(summary.comparison)}
        </span>
        <span className="tabular-nums">
          {plural(studies.length, 'study', 'studies')}
        </span>
        {counter > 0 ? (
          <span className="font-medium text-tone-negative tabular-nums">
            {counter} opposing, null, or mixed
          </span>
        ) : null}
      </p>
    </header>
  );
}
