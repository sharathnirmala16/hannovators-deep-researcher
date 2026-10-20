import { useEvidenceSelection } from '@/domains/evidence';
import {
  studyLabel,
  type ClaimView,
  type SourceView,
  type WorkspaceState,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { TableCell, TableRow } from '@/shared/ui/table';
import { Tag } from '@/shared/ui/tag';

import { VERDICT, contradictions } from '../model/evidence';
import { ClaimCell } from './ClaimCell';
import { Confidence } from './Confidence';
import { humanize } from './findings';
import { StudyCell } from './StudyCell';
import { SELECTED_ROW } from './tableStyles';

interface ClaimRowProps {
  claim: ClaimView;
  state: WorkspaceState;
  sources: ReadonlyMap<string, SourceView>;
}

/** One claim: its source, label, and text; contradicting claims below. */
export function ClaimRow({ claim, state, sources }: ClaimRowProps) {
  const { selection } = useEvidenceSelection();
  const source = claim.source_id ? sources.get(claim.source_id) : undefined;
  const against = contradictions(claim, state.claims);
  const verdict = VERDICT[claim.verdict];
  const selected =
    (selection.kind === 'claim' || selection.kind === 'highlight') &&
    selection.claimId === claim.id;
  const nameOf = (id: string | null) => {
    const other = id ? sources.get(id) : undefined;
    return other ? studyLabel(other) : 'an unlisted source';
  };
  return (
    <TableRow
      data-state={selected ? 'selected' : undefined}
      className={cn('hover:bg-transparent', selected && SELECTED_ROW)}
    >
      <TableCell className="align-top whitespace-normal">
        <div className="flex min-w-0 flex-col gap-1">
          {source ? (
            <StudyCell source={source} compact />
          ) : (
            <span className="text-xs text-muted-foreground">No source</span>
          )}
          <span className="text-xs text-muted-foreground">
            {humanize(claim.label)}
          </span>
          <ClaimCell
            claim={claim}
            highlights={state.highlights}
            className="reading max-w-[72ch] text-sm leading-[22px] text-foreground"
          />
          {against.length > 0 ? (
            <p className="mt-1 text-xs text-muted-foreground">
              <span className="font-semibold text-tone-negative">
                Contradicted by{' '}
              </span>
              {against.map((other, index) => (
                <span key={other.id}>
                  {index > 0 ? ', ' : null}
                  <ClaimCell claim={other} highlights={state.highlights}>
                    {humanize(other.label)}
                  </ClaimCell>{' '}
                  ({nameOf(other.source_id)})
                </span>
              ))}
            </p>
          ) : null}
        </div>
      </TableCell>
      <TableCell className="align-top">
        <Tag tone={verdict.tone}>{verdict.label}</Tag>
      </TableCell>
      <TableCell className="pt-2.5 align-top">
        <Confidence value={claim.confidence} />
      </TableCell>
    </TableRow>
  );
}
