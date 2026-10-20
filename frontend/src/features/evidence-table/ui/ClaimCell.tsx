import type { ReactNode } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import {
  useWorkspace,
  type ClaimView,
  type HighlightView,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { MARK_BUTTON, markClasses } from './marker';

interface ClaimCellProps {
  claim: ClaimView;
  highlights: readonly HighlightView[];
  children?: ReactNode;
  className?: string;
}

/**
 * A value that opens its highlighted sentence in the source. A value with a
 * source passage carries the marker underline; the selected value carries
 * the marker stroke, like the rectangles on the PDF page.
 */
export function ClaimCell({
  claim,
  highlights,
  children,
  className,
}: ClaimCellProps) {
  const { selection, selectClaim } = useEvidenceSelection();
  const { recordAction } = useWorkspace();
  const active =
    (selection.kind === 'claim' || selection.kind === 'highlight') &&
    selection.claimId === claim.id;
  const traceable = claim.highlight_ids.length > 0 || claim.quote !== null;

  const open = () => {
    selectClaim(claim, highlights);
    recordAction({
      name: 'user.claim.open',
      summary: `Opened ${claim.label}`,
      target: claim.id,
      source_ids: claim.source_id ? [claim.source_id] : [],
      details: { claim_id: claim.id, kind: claim.kind },
    });
  };

  return (
    <button
      type="button"
      onClick={open}
      aria-pressed={active}
      title={claim.quote ?? claim.text}
      className={cn(MARK_BUTTON, className)}
    >
      <span className={markClasses(active, traceable)}>
        {children ?? claim.text}
      </span>
    </button>
  );
}
