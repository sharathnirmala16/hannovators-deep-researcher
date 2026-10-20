import { useMemo } from 'react';

import {
  useEvidenceSelection,
  type EvidenceSelection,
} from '@/domains/evidence';
import { useWorkspace, type WorkspaceState } from '@/domains/workspace';
import { EmptyState } from '@/shared/ui/states';

import {
  isSnapshot,
  resolveSource,
  sourcePdfUrl,
  type ResolvedSource,
} from '../model/resolveSource';
import { viewerTarget } from '../model/targets';
import { PdfDocumentView } from './PdfDocumentView';
import { SnapshotView } from './SnapshotView';
import { SourceSwitcher } from './SourceSwitcher';

function selectionQuote(
  selection: EvidenceSelection,
  resolved: ResolvedSource,
): string | null {
  if (selection.kind === 'citation') return selection.quote || null;
  return resolved.claim?.quote ?? null;
}

function SourceHeading({
  resolved,
  selection,
}: {
  resolved: ResolvedSource;
  selection: EvidenceSelection;
}) {
  const { source, claim, page } = resolved;
  const meta = [source.venue, source.year, page ? `page ${page}` : null]
    .filter(Boolean)
    .join(', ');
  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm leading-snug font-medium">{source.title}</p>
      {meta ? <p className="text-xs text-muted-foreground">{meta}</p> : null}
      {claim ? (
        <p className="border-l-2 border-marker-ink pl-2 text-xs">
          <span className="font-medium">{claim.label}:</span> {claim.text}
        </p>
      ) : null}
      {selection.kind === 'citation' ? (
        <p className="line-clamp-3 border-l-2 border-marker-ink pl-2 text-xs">
          <span className="font-medium">Citation [{selection.n}]:</span>{' '}
          {selection.quote}
        </p>
      ) : null}
    </div>
  );
}

function OriginalLink({ href }: { href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="underline underline-offset-4 hover:text-foreground"
    >
      Open the original
    </a>
  );
}

function SourceBody({ state }: { state: WorkspaceState }) {
  const { selection } = useEvidenceSelection();
  const resolved = useMemo(
    () => resolveSource(selection, state),
    [selection, state],
  );
  const target = useMemo(
    () =>
      resolved ? viewerTarget(selection, state, resolved.source.id) : null,
    [selection, state, resolved],
  );
  if (!resolved || !target) {
    return (
      <div className="scroll-y min-h-0 flex-1 p-4">
        <EmptyState title="No source selected">
          Click a citation number in the chat, a claim in the evidence table, a
          node in the graph, or choose a source above. It opens here with the
          supporting passage highlighted.
        </EmptyState>
      </div>
    );
  }
  const { source } = resolved;
  const url = sourcePdfUrl(source);
  if (url && !isSnapshot(source)) {
    return (
      <PdfDocumentView
        key={url}
        url={url}
        target={target}
        trigger={selection}
      />
    );
  }
  const quote = selectionQuote(selection, resolved);
  if (isSnapshot(source)) {
    return (
      <div className="scroll-y min-h-0 flex-1 p-4">
        <SnapshotView url={source.raw_url} quote={quote} />
      </div>
    );
  }
  return (
    <div className="scroll-y min-h-0 flex-1 p-4">
      <EmptyState title="This source has no PDF">
        <p>The full text was not downloaded, so there is nothing to show.</p>
        {quote ? (
          <blockquote className="mt-2 font-serif">{quote}</blockquote>
        ) : null}
        {source.url ? <OriginalLink href={source.url} /> : null}
      </EmptyState>
    </div>
  );
}

/** The selected source: the PDF with highlights, or the web snapshot. */
export function PdfViewer() {
  const { load } = useWorkspace();
  const { selection, selectSource } = useEvidenceSelection();
  if (load.status !== 'ready') return null;
  const value = selection.kind === 'none' ? '' : selection.sourceId;
  const resolved = resolveSource(selection, load.state);
  return (
    <section
      aria-labelledby="pdf-viewer-title"
      className="flex min-h-0 flex-1 flex-col"
    >
      <h2 id="pdf-viewer-title" className="sr-only">
        Source viewer
      </h2>
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3">
        <SourceSwitcher
          state={load.state}
          value={value ?? ''}
          onChange={(sourceId) => selectSource(sourceId)}
        />
        {resolved ? (
          <SourceHeading resolved={resolved} selection={selection} />
        ) : null}
      </div>
      <SourceBody state={load.state} />
    </section>
  );
}
