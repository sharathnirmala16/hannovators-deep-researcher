import type { SourceView, WorkspaceState } from '@/domains/workspace';
import { EmptyState } from '@/shared/ui/states';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';

import {
  byEvidenceRank,
  downgradeReasons,
  indexById,
  studyClaims,
} from '../model/evidence';
import { CertaintyBadge } from './CertaintyBadge';
import { ClaimCell } from './ClaimCell';
import { RobLights } from './RobLights';
import { StudyCell } from './StudyCell';

type Summary = NonNullable<
  WorkspaceState['synthesis']
>['pairwise_summaries'][number];

function StudyRow({
  source,
  state,
}: {
  source: SourceView;
  state: WorkspaceState;
}) {
  const { intervention, comparison, others } = studyClaims(
    state.claims,
    source.id,
  );
  const venue = [
    source.venue,
    source.directness === 'INDIRECT' ? 'indirect' : null,
  ]
    .filter(Boolean)
    .join(', ');
  return (
    <TableRow>
      <TableCell className="w-[38%] max-w-0 align-top">
        <StudyCell source={source} detail={venue} />
      </TableCell>
      <TableCell className="align-top">
        <RobLights rob2={source.rob2} />
      </TableCell>
      <TableCell className="align-top font-medium whitespace-nowrap">
        {intervention && comparison ? (
          <span className="inline-flex items-baseline gap-1">
            <ClaimCell claim={intervention} highlights={state.highlights} />
            <span className="text-xs font-normal text-muted-foreground">
              vs
            </span>
            <ClaimCell claim={comparison} highlights={state.highlights} />
          </span>
        ) : (
          <span className="text-xs font-normal text-muted-foreground">
            Not reported
          </span>
        )}
      </TableCell>
      <TableCell className="align-top">
        <div className="flex flex-col items-start gap-1">
          {others.map((claim) => (
            <ClaimCell
              key={claim.id}
              claim={claim}
              highlights={state.highlights}
              className="text-xs"
            />
          ))}
        </div>
      </TableCell>
    </TableRow>
  );
}

function OutcomeProfile({
  summary,
  state,
}: {
  summary: Summary;
  state: WorkspaceState;
}) {
  const sources = indexById(state.sources);
  const studies = summary.source_ids
    .map((id) => sources.get(id))
    .filter((source) => source !== undefined)
    .sort(byEvidenceRank);
  const reasons = downgradeReasons(summary.grade);
  return (
    <section className="flex flex-col border-b py-4 last:border-b-0">
      <header className="flex items-start gap-4 px-4 pb-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold">{summary.outcome}</h3>
          <p className="text-xs text-muted-foreground">
            {summary.intervention} vs {summary.comparison}
          </p>
        </div>
        <CertaintyBadge certainty={summary.grade.certainty} />
      </header>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[38%]">Study</TableHead>
            <TableHead className="w-28">RoB 2</TableHead>
            <TableHead className="w-32">Events (I vs C)</TableHead>
            <TableHead>Effect</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {studies.map((source) => (
            <StudyRow key={source.id} source={source} state={state} />
          ))}
        </TableBody>
      </Table>
      <div className="flex flex-col gap-1 px-4 pt-2 text-sm">
        <p>{summary.summary}</p>
        {reasons.length > 0 ? (
          <ul className="flex flex-col gap-0.5 text-xs">
            {reasons.map((reason) => (
              <li key={reason.domain}>
                <span className="font-medium text-tone-caution">
                  Downgraded for {reason.domain.toLowerCase()}.
                </span>{' '}
                {reason.text}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No downgrades.</p>
        )}
      </div>
    </section>
  );
}

/** MEDICAL: GRADE evidence profile, one block per synthesized outcome. */
export function EvidenceProfile({ state }: { state: WorkspaceState }) {
  const summaries = state.synthesis?.pairwise_summaries ?? [];
  if (summaries.length === 0) {
    return (
      <EmptyState className="mx-4" title="No evidence profile yet">
        The GRADE profile appears after the synthesis stage.
      </EmptyState>
    );
  }
  return (
    <div className="flex flex-col">
      {summaries.map((summary) => (
        <OutcomeProfile
          key={`${summary.intervention}|${summary.comparison}|${summary.outcome}`}
          summary={summary}
          state={state}
        />
      ))}
    </div>
  );
}
