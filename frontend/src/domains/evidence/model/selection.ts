/**
 * Evidence selection: claim -> highlight -> source + page. The input types are
 * structural, so `ClaimView` and `HighlightView` from the workspace domain fit
 * without a cross-domain import.
 */

export interface SelectableClaim {
  readonly id: string;
  readonly source_id: string | null;
  readonly highlight_ids: readonly string[];
}

export interface SelectableHighlight {
  readonly id: string;
  readonly source_id: string;
  readonly claim_id: string;
  readonly page: number;
}

export type EvidenceSelection =
  | { kind: 'none' }
  /** A source, optionally at a 1-based page (for example from the graph). */
  | { kind: 'source'; sourceId: string; page: number | null }
  /** A claim with no highlight (for example the recommendation). */
  | { kind: 'claim'; claimId: string; sourceId: string | null }
  | {
      kind: 'highlight';
      claimId: string;
      highlightId: string;
      sourceId: string;
      page: number;
    };

export const NO_SELECTION: EvidenceSelection = { kind: 'none' };

export function highlightSelection(
  highlight: SelectableHighlight,
): EvidenceSelection {
  return {
    kind: 'highlight',
    claimId: highlight.claim_id,
    highlightId: highlight.id,
    sourceId: highlight.source_id,
    page: highlight.page,
  };
}

/** Selects the claim's first known highlight, else the claim alone. */
export function claimSelection(
  claim: SelectableClaim,
  highlights: readonly SelectableHighlight[],
): EvidenceSelection {
  for (const id of claim.highlight_ids) {
    const highlight = highlights.find((item) => item.id === id);
    if (highlight) return highlightSelection(highlight);
  }
  return { kind: 'claim', claimId: claim.id, sourceId: claim.source_id };
}

export function sourceSelection(
  sourceId: string,
  page: number | null = null,
): EvidenceSelection {
  return { kind: 'source', sourceId, page };
}
