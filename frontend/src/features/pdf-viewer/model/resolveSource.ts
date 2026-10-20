import type { EvidenceSelection } from '@/domains/evidence';
import type {
  ClaimView,
  SourceView,
  WorkspaceState,
} from '@/domains/workspace';

export interface ResolvedSource {
  source: SourceView;
  /** 1-based page to open, or null when the selection names none. */
  page: number | null;
  claim: ClaimView | undefined;
}

function selectedSourceId(selection: EvidenceSelection): string | null {
  return selection.kind === 'none' ? null : selection.sourceId;
}

function selectedPage(selection: EvidenceSelection): number | null {
  switch (selection.kind) {
    case 'highlight':
    case 'source':
    case 'citation':
      return selection.page;
    default:
      return null;
  }
}

/** Turns the evidence selection into a source, page, and claim. */
export function resolveSource(
  selection: EvidenceSelection,
  state: WorkspaceState,
): ResolvedSource | null {
  const sourceId = selectedSourceId(selection);
  const source = state.sources.find((item) => item.id === sourceId);
  if (!source) return null;
  const claim =
    selection.kind === 'highlight' || selection.kind === 'claim'
      ? state.claims.find((item) => item.id === selection.claimId)
      : undefined;
  return { source, page: selectedPage(selection), claim };
}

const PDF_PATH = /\.pdf$/i;

/**
 * The source PDF to render. The raw file comes first: the viewer draws the
 * highlights itself, so the annotated copy would show them twice.
 */
export function sourcePdfUrl(source: SourceView): string | null {
  for (const url of [source.raw_url, source.highlighted_url]) {
    const base = url?.split('#')[0];
    if (base && PDF_PATH.test(base)) return base;
  }
  return null;
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
