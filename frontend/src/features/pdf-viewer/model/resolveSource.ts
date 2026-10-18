import type { EvidenceSelection } from '@/domains/evidence';
import type {
  ClaimView,
  HighlightView,
  SourceView,
  WorkspaceState,
} from '@/domains/workspace';

export interface ResolvedSource {
  source: SourceView;
  page: number;
  claim: ClaimView | undefined;
  highlight: HighlightView | undefined;
}

function selectedSourceId(selection: EvidenceSelection): string | null {
  return selection.kind === 'none' ? null : selection.sourceId;
}

/** Turns the evidence selection into a source, page, claim, and highlight. */
export function resolveSource(
  selection: EvidenceSelection,
  state: WorkspaceState,
): ResolvedSource | null {
  const sourceId = selectedSourceId(selection);
  const source = state.sources.find((item) => item.id === sourceId);
  if (!source) return null;
  const highlight =
    selection.kind === 'highlight'
      ? state.highlights.find((item) => item.id === selection.highlightId)
      : undefined;
  const claim =
    selection.kind === 'highlight' || selection.kind === 'claim'
      ? state.claims.find((item) => item.id === selection.claimId)
      : undefined;
  const page =
    selection.kind === 'highlight' || selection.kind === 'source'
      ? (selection.page ?? 1)
      : 1;
  return { source, page, claim, highlight };
}

const PDF_PATH = /\.pdf(#.*)?$/i;

/** PDF URL at the page, preferring the highlight's own URL. */
export function pdfUrl({
  source,
  page,
  highlight,
}: ResolvedSource): string | null {
  const base = (
    highlight?.pdf_url ??
    source.highlighted_url ??
    source.raw_url
  )?.split('#')[0];
  if (!base || !PDF_PATH.test(base)) return null;
  return `${base}#page=${page}`;
}

export function isSnapshot(source: SourceView): boolean {
  return source.origin === 'WEB' || (source.raw_url?.endsWith('.md') ?? false);
}

/** Sources worth reading: seeds and those promoted by screening or appraisal. */
export function promotedSources(state: WorkspaceState): SourceView[] {
  return state.sources.filter(
    (source) =>
      source.status === 'APPRAISE_PROMOTED' ||
      source.status === 'SCREEN_PROMOTED' ||
      source.status === 'SEED',
  );
}
