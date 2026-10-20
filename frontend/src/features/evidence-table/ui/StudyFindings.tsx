import type { ClaimView, HighlightView } from '@/domains/workspace';
import { plural } from '@/shared/lib/format';

import { ClaimCell } from './ClaimCell';
import { Finding } from './Finding';
import { outcomeFindings } from './findings';

interface StudyFindingsProps {
  claims: readonly ClaimView[];
  highlights: readonly HighlightView[];
  sourceId: string;
  outcome: string;
}

/**
 * A study's results for one outcome: event counts per arm, the effect and
 * other findings, and (folded) its results for other outcomes.
 */
export function StudyFindings({
  claims,
  highlights,
  sourceId,
  outcome,
}: StudyFindingsProps) {
  const { events, findings, others } = outcomeFindings(
    claims,
    sourceId,
    outcome,
  );
  return (
    <div className="flex min-w-0 flex-col gap-2">
      {events ? (
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-muted-foreground">
            Events, intervention vs comparison
          </span>
          <span className="flex flex-wrap items-baseline gap-x-2 text-sm font-medium tabular-nums">
            <ClaimCell claim={events[0]} highlights={highlights} />
            <span className="text-xs font-normal text-muted-foreground">
              vs
            </span>
            <ClaimCell claim={events[1]} highlights={highlights} />
          </span>
        </div>
      ) : null}
      {findings.map((claim) => (
        <Finding key={claim.id} claim={claim} highlights={highlights} />
      ))}
      {!events && findings.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No result for this outcome was extracted.
        </p>
      ) : null}
      {others.length > 0 ? (
        <details>
          <summary className="w-fit cursor-pointer rounded-sm text-xs text-muted-foreground transition-colors hover:text-foreground">
            {plural(others.length, 'result')} for other outcomes
          </summary>
          <div className="mt-2 flex flex-col gap-2">
            {others.map((claim) => (
              <Finding key={claim.id} claim={claim} highlights={highlights} />
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
