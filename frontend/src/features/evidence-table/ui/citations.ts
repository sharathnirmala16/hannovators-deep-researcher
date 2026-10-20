import {
  evidenceRank,
  type SourceView,
  type WorkspaceState,
} from '@/domains/workspace';

export type CitedSegment =
  | { kind: 'text'; text: string }
  | { kind: 'source'; source: SourceView; key: string };

export interface CitationIndex {
  byId: ReadonlyMap<string, SourceView>;
  /** "S1", "S2", ...: the labels the synthesis model saw. */
  byLabel: ReadonlyMap<string, SourceView>;
}

/**
 * The synthesis cites sources as `[<source id>]`. Older runs kept the model's
 * labels (`S1`), numbered over the included sources, strongest design first.
 */
export function citationIndex(state: WorkspaceState): CitationIndex {
  const included = state.sources
    .filter((source) => source.status === 'APPRAISE_PROMOTED')
    .sort((a, b) => evidenceRank(a) - evidenceRank(b));
  return {
    byId: new Map(state.sources.map((source) => [source.id, source])),
    byLabel: new Map(
      included.map((source, index) => [`S${index + 1}`, source]),
    ),
  };
}

const CITATION =
  /\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]|\bS\d+\b/gi;

/** Splits prose into text runs and source citations. */
export function citedSegments(
  text: string,
  index: CitationIndex,
): CitedSegment[] {
  const segments: CitedSegment[] = [];
  let last = 0;
  for (const match of text.matchAll(CITATION)) {
    const source = match[1]
      ? index.byId.get(match[1].toLowerCase())
      : index.byLabel.get(match[0].toUpperCase());
    if (!source) continue;
    if (match.index > last) {
      segments.push({ kind: 'text', text: text.slice(last, match.index) });
    }
    segments.push({ kind: 'source', source, key: `${match.index}` });
    last = match.index + match[0].length;
  }
  if (last < text.length)
    segments.push({ kind: 'text', text: text.slice(last) });
  return segments;
}
