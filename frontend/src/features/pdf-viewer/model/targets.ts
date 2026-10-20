import type { EvidenceSelection } from '@/domains/evidence';
import type { HighlightView, WorkspaceState } from '@/domains/workspace';

import type { PageRect } from './geometry';

/** What the document view shows for the current selection. */
export interface ViewerTarget {
  /** Page to open, or null to stay at the top (or follow the rects). */
  page: number | null;
  /** The selected claim's or citation's rects, drawn strongly. */
  active: PageRect[];
  /** Other claim highlights in this source, drawn faintly. */
  faint: PageRect[];
  /** Text to search for when there are no rects. */
  quote: string | null;
}

function toPageRects(highlights: readonly HighlightView[]): PageRect[] {
  return highlights.flatMap((highlight) =>
    highlight.rects.map((rect) => ({ page: highlight.page, rect })),
  );
}

function claimQuote(state: WorkspaceState, claimId: string): string | null {
  return state.claims.find((claim) => claim.id === claimId)?.quote ?? null;
}

/** The selected highlight first, then the claim's other highlights. */
function claimTarget(
  highlights: readonly HighlightView[],
  claimId: string,
  highlightId: string | null,
): PageRect[] {
  const own = highlights.filter((item) => item.claim_id === claimId);
  const selected = own.filter((item) => item.id === highlightId);
  const others = own.filter((item) => item.id !== highlightId);
  return toPageRects([...selected, ...others]);
}

function citationRects(
  selection: Extract<EvidenceSelection, { kind: 'citation' }>,
): PageRect[] {
  const { page } = selection;
  if (page === null) return [];
  return selection.rects.map((rect) => ({ page, rect }));
}

/** Rects and fallback quote for the selection, scoped to one source. */
export function viewerTarget(
  selection: EvidenceSelection,
  state: WorkspaceState,
  sourceId: string,
): ViewerTarget {
  const highlights = state.highlights.filter(
    (item) => item.source_id === sourceId && item.rects.length > 0,
  );
  const claimId =
    selection.kind === 'highlight' || selection.kind === 'claim'
      ? selection.claimId
      : null;
  const faint = toPageRects(
    highlights.filter((item) => item.claim_id !== claimId),
  );
  switch (selection.kind) {
    case 'highlight':
    case 'claim': {
      const highlightId =
        selection.kind === 'highlight' ? selection.highlightId : null;
      const active = claimTarget(highlights, selection.claimId, highlightId);
      const page =
        selection.kind === 'highlight'
          ? selection.page
          : (active[0]?.page ?? null);
      const quote = claimQuote(state, selection.claimId);
      return { page, active, faint, quote };
    }
    case 'citation':
      return {
        page: selection.page,
        active: citationRects(selection),
        faint,
        quote: selection.quote || null,
      };
    case 'source':
      return { page: selection.page, active: [], faint, quote: null };
    default:
      return { page: null, active: [], faint, quote: null };
  }
}
