import type { ReactNode } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import type { ClaimView, HighlightView } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

interface ClaimCellProps {
  claim: ClaimView;
  highlights: readonly HighlightView[];
  children?: ReactNode;
  className?: string;
}

/** A value that opens its highlighted source text when clicked. */
export function ClaimCell({
  claim,
  highlights,
  children,
  className,
}: ClaimCellProps) {
  const { selection, selectClaim } = useEvidenceSelection();
  const active =
    selection.kind !== 'none' && selection.kind !== 'source'
      ? selection.claimId === claim.id
      : false;
  const grounded = claim.highlight_ids.length > 0;
  return (
    <button
      type="button"
      onClick={() => selectClaim(claim, highlights)}
      aria-pressed={active}
      title={claim.quote ?? claim.text}
      className={cn(
        'rounded-sm px-1 py-0.5 text-left tabular-nums underline decoration-dotted decoration-1 underline-offset-4 transition-colors',
        'hover:bg-yellow-100 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        grounded ? 'decoration-foreground/40' : 'decoration-transparent',
        active && 'bg-yellow-200 decoration-yellow-700 hover:bg-yellow-200',
        className,
      )}
    >
      {children ?? claim.text}
    </button>
  );
}
