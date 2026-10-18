import {
  studyLabel,
  type ClaimVerdict,
  type WorkspaceState,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';

import { contradictions, groupByOutcome, indexById } from '../model/evidence';
import { ClaimCell } from './ClaimCell';

const VERDICT: Record<ClaimVerdict, { label: string; className: string }> = {
  SUPPORTED: {
    label: 'Supported',
    className: 'bg-shade-2 text-tone-positive',
  },
  CONTRADICTED: {
    label: 'Contradicted',
    className: 'bg-shade-2 text-tone-negative',
  },
  MIXED: {
    label: 'Mixed',
    className: 'bg-shade-2 text-tone-caution',
  },
  UNVERIFIED: {
    label: 'Unverified',
    className: 'bg-muted text-muted-foreground',
  },
};

function Confidence({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground">n/a</span>;
  const percent = Math.round(value * 100);
  return (
    <span className="inline-flex items-center gap-2 tabular-nums">
      <span className="h-1.5 w-12 overflow-hidden rounded-full bg-muted">
        <span
          className="block h-full bg-shade-6"
          style={{ width: `${percent}%` }}
        />
      </span>
      {percent}%
    </span>
  );
}

/** GENERAL: one row per claim with verdict, confidence, source, conflicts. */
export function ClaimMatrix({ state }: { state: WorkspaceState }) {
  const sources = indexById(state.sources);
  const groups = groupByOutcome(state.claims);
  if (groups.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Claims appear after the synthesis stage.
      </p>
    );
  }
  const label = (sourceId: string | null) => {
    const source = sourceId ? sources.get(sourceId) : undefined;
    return source ? studyLabel(source) : 'Unknown source';
  };
  return (
    <div className="flex flex-col gap-4">
      {groups.map(([outcome, claims]) => (
        <section key={outcome} className="flex flex-col">
          <h3 className="border-b py-2 text-sm font-semibold">{outcome}</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Claim</TableHead>
                <TableHead>Verdict</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Contradicted by</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {claims.map((claim) => {
                const verdict = VERDICT[claim.verdict];
                const against = contradictions(claim, state.claims);
                return (
                  <TableRow key={claim.id}>
                    <TableCell className="max-w-72 align-top whitespace-normal">
                      <div className="text-xs text-muted-foreground">
                        {claim.label}
                      </div>
                      <ClaimCell claim={claim} highlights={state.highlights} />
                    </TableCell>
                    <TableCell className="align-top">
                      <span
                        className={cn(
                          'rounded-sm px-2 py-0.5 text-xs font-medium',
                          verdict.className,
                        )}
                      >
                        {verdict.label}
                      </span>
                    </TableCell>
                    <TableCell className="align-top text-xs">
                      <Confidence value={claim.confidence} />
                    </TableCell>
                    <TableCell className="max-w-40 truncate align-top text-xs">
                      {label(claim.source_id)}
                    </TableCell>
                    <TableCell className="max-w-48 align-top text-xs whitespace-normal">
                      {against.length === 0 ? (
                        <span className="text-muted-foreground">None</span>
                      ) : (
                        against.map((other) => (
                          <div key={other.id}>
                            <ClaimCell
                              claim={other}
                              highlights={state.highlights}
                            >
                              {other.label}
                            </ClaimCell>
                            <span className="text-muted-foreground">
                              {' '}
                              ({label(other.source_id)})
                            </span>
                          </div>
                        ))
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </section>
      ))}
    </div>
  );
}
