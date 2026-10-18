import type { WorkspaceState } from '@/domains/workspace';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';

import {
  downgradeReasons,
  indexById,
  studyClaims,
  studyLabel,
} from '../model/evidence';
import { CertaintyBadge } from './CertaintyBadge';
import { ClaimCell } from './ClaimCell';
import { RobLights } from './RobLights';

type Summary = NonNullable<
  WorkspaceState['synthesis']
>['pairwise_summaries'][number];

interface OutcomeProfileProps {
  summary: Summary;
  state: WorkspaceState;
}

function OutcomeProfile({ summary, state }: OutcomeProfileProps) {
  const sources = indexById(state.sources);
  const reasons = downgradeReasons(summary.grade);
  return (
    <section className="rounded-lg border bg-card">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h3 className="text-sm leading-snug font-semibold">
            {summary.outcome}
          </h3>
          <p className="text-xs text-muted-foreground">
            {summary.intervention} vs {summary.comparison}
          </p>
        </div>
        <CertaintyBadge certainty={summary.grade.certainty} />
      </header>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Study</TableHead>
            <TableHead>RoB 2</TableHead>
            <TableHead>Events (I vs C)</TableHead>
            <TableHead>Effect</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {summary.source_ids.map((sourceId) => {
            const source = sources.get(sourceId);
            if (!source) return null;
            const { intervention, comparison, others } = studyClaims(
              state.claims,
              sourceId,
            );
            return (
              <TableRow key={sourceId}>
                <TableCell className="max-w-48 align-top">
                  <div className="font-medium">{studyLabel(source)}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {source.venue}
                    {source.directness === 'INDIRECT' ? ', indirect' : ''}
                  </div>
                </TableCell>
                <TableCell className="align-top">
                  <RobLights rob2={source.rob2} />
                </TableCell>
                <TableCell className="align-top font-medium">
                  {intervention && comparison ? (
                    <span className="inline-flex items-baseline gap-1">
                      <ClaimCell
                        claim={intervention}
                        highlights={state.highlights}
                      />
                      <span className="text-xs text-muted-foreground">vs</span>
                      <ClaimCell
                        claim={comparison}
                        highlights={state.highlights}
                      />
                    </span>
                  ) : (
                    <span className="text-muted-foreground">Not reported</span>
                  )}
                </TableCell>
                <TableCell className="align-top whitespace-normal">
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
          })}
        </TableBody>
      </Table>
      <footer className="space-y-1 border-t px-4 py-3 text-xs">
        <p>{summary.summary}</p>
        {reasons.length > 0 ? (
          <ul className="space-y-0.5 text-amber-900">
            {reasons.map((reason) => (
              <li key={reason.domain}>
                <span className="font-semibold">
                  Downgraded for {reason.domain.toLowerCase()}.
                </span>{' '}
                {reason.text}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground">No downgrades.</p>
        )}
      </footer>
    </section>
  );
}

/** MEDICAL: GRADE evidence profile, one block per synthesized outcome. */
export function EvidenceProfile({ state }: { state: WorkspaceState }) {
  const summaries = state.synthesis?.pairwise_summaries ?? [];
  if (summaries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        The evidence profile appears after the synthesis stage.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {summaries.map((summary) => (
        <OutcomeProfile
          key={`${summary.intervention}|${summary.outcome}`}
          summary={summary}
          state={state}
        />
      ))}
    </div>
  );
}
