import { useId } from 'react';

import {
  evidenceRank,
  type ClaimView,
  type SourceView,
  type WorkspaceState,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { plural } from '@/shared/lib/format';
import { plainMath } from '@/shared/lib/plainMath';
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';

import { ClaimRow } from './ClaimRow';
import { STICKY_HEAD, STICKY_TABLE } from './tableStyles';

interface ClaimGroupProps {
  outcome: string;
  claims: readonly ClaimView[];
  state: WorkspaceState;
  sources: ReadonlyMap<string, SourceView>;
}

function rankOf(
  claim: ClaimView,
  sources: ReadonlyMap<string, SourceView>,
): number {
  const source = claim.source_id ? sources.get(claim.source_id) : undefined;
  return source ? evidenceRank(source) : Number.MAX_SAFE_INTEGER;
}

/** One outcome of the claim matrix: a table of its claims. */
export function ClaimGroup({
  outcome,
  claims,
  state,
  sources,
}: ClaimGroupProps) {
  const titleId = useId();
  // Strongest source first; a source's claims stay together.
  const ranked = [...claims].sort(
    (a, b) =>
      rankOf(a, sources) - rankOf(b, sources) ||
      (a.source_id ?? '').localeCompare(b.source_id ?? ''),
  );
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-2">
      <header className="flex items-baseline gap-3 px-4">
        <h3
          id={titleId}
          className="reading min-w-0 flex-1 text-base font-semibold text-foreground"
        >
          {plainMath(outcome)}
        </h3>
        <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
          {plural(claims.length, 'claim')}
        </span>
      </header>
      <Table className={STICKY_TABLE}>
        <TableHeader>
          <TableRow>
            <TableHead className={STICKY_HEAD}>Source and claim</TableHead>
            <TableHead className={cn(STICKY_HEAD, 'w-28')}>Verdict</TableHead>
            <TableHead className={cn(STICKY_HEAD, 'w-24')}>
              Confidence
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {ranked.map((claim) => (
            <ClaimRow
              key={claim.id}
              claim={claim}
              state={state}
              sources={sources}
            />
          ))}
        </TableBody>
      </Table>
    </section>
  );
}
