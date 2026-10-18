import type { ReactNode } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import {
  useWorkspace,
  type ClaimView,
  type HighlightView,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

interface ClaimCellProps {
  claim: ClaimView;
  highlights: readonly HighlightView[];
  children?: ReactNode;
  className?: string;
}

/**
 * A value that opens its highlighted sentence in the source. The selected
 * value carries the marker stroke, like the rectangles on the PDF page.
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
  const grounded = claim.highlight_ids.length > 0;

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
      className={cn(
        'rounded-sm px-0.5 text-left tabular-nums underline decoration-1 underline-offset-4 transition-colors',
        'hover:bg-marker/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        grounded
          ? 'decoration-foreground/30 decoration-dotted'
          : 'decoration-transparent',
        active && 'marked decoration-marker-ink hover:bg-marker',
        className,
      )}
    >
      {children ?? claim.text}
    </button>
  );
}
