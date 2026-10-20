import { useId } from 'react';

import type { Synthesis, WorkspaceState } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';

import { byEvidenceRank, downgradeReasons, indexById } from '../model/evidence';
import type { CitationIndex } from './citations';
import { CitedText } from './CitedText';
import { OutcomeHeader } from './OutcomeHeader';
import { StudyRow } from './StudyRow';
import { STICKY_HEAD, STICKY_TABLE } from './tableStyles';

type Summary = Synthesis['pairwise_summaries'][number];

interface OutcomeProfileProps {
  summary: Summary;
  state: WorkspaceState;
  citations: CitationIndex;
}

/** One outcome: its comparison and certainty, the studies, the summary. */
export function OutcomeProfile({
  summary,
  state,
  citations,
}: OutcomeProfileProps) {
  const titleId = useId();
  const sources = indexById(state.sources);
  const studies = summary.source_ids
    .map((id) => sources.get(id))
    .filter((source) => source !== undefined)
    .sort(byEvidenceRank);
  const reasons = downgradeReasons(summary.grade);
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-3">
      <OutcomeHeader summary={summary} studies={studies} titleId={titleId} />
      {studies.length > 0 ? (
        <Table className={STICKY_TABLE}>
          <TableHeader>
            <TableRow>
              <TableHead className={STICKY_HEAD}>Study and results</TableHead>
              <TableHead className={cn(STICKY_HEAD, 'w-32')}>
                Risk of bias
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {studies.map((source) => (
              <StudyRow
                key={source.id}
                source={source}
                state={state}
                outcome={summary.outcome}
              />
            ))}
          </TableBody>
        </Table>
      ) : null}
      <div className="flex flex-col gap-2 px-4">
        <p className="reading max-w-[72ch] text-sm leading-[22px] text-foreground">
          <CitedText text={summary.summary} citations={citations} />
        </p>
        {reasons.length > 0 ? (
          <ul className="flex flex-col gap-0.5 text-xs">
            {reasons.map((reason) => (
              <li key={reason.domain} className="max-w-[72ch]">
                <span className="font-semibold text-tone-caution">
                  Downgraded for {reason.domain.toLowerCase()}
                </span>
                <span className="text-muted-foreground">: {reason.text}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">Not downgraded.</p>
        )}
      </div>
    </section>
  );
}
