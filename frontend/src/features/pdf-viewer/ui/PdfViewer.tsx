import { useEvidenceSelection } from '@/domains/evidence';
import { useWorkspace, type WorkspaceState } from '@/domains/workspace';

import {
  isSnapshot,
  pdfUrl,
  promotedSources,
  resolveSource,
} from '../model/resolveSource';
import { SnapshotView } from './SnapshotView';

function SourceSwitcher({
  state,
  value,
  onChange,
}: {
  state: WorkspaceState;
  value: string;
  onChange: (sourceId: string) => void;
}) {
  const options = promotedSources(state);
  const known = options.some((source) => source.id === value);
  return (
    <label className="flex flex-col gap-1 text-xs text-muted-foreground">
      Source
      <select
        value={known ? value : ''}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 rounded-md border bg-background px-2 text-sm text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <option value="" disabled>
          Choose a promoted source
        </option>
        {options.map((source) => (
          <option key={source.id} value={source.id}>
            {source.title}
          </option>
        ))}
      </select>
    </label>
  );
}

function SourceBody({ state }: { state: WorkspaceState }) {
  const { selection } = useEvidenceSelection();
  const resolved = resolveSource(selection, state);
  if (!resolved) {
    return (
      <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
        Click a number or claim in the evidence table, a node in the graph, or
        choose a source above. The source opens here at the highlighted page.
      </div>
    );
  }
  const { source, claim, page } = resolved;
  const url = pdfUrl(resolved);
  return (
    <div className="flex flex-col gap-2">
      <div>
        <p className="text-sm leading-snug font-medium">{source.title}</p>
        <p className="text-xs text-muted-foreground">
          {[source.venue, source.year].filter(Boolean).join(', ')}
          {url ? `, page ${page}` : ''}
        </p>
      </div>
      {claim ? (
        <p className="border-l-2 border-yellow-400 pl-2 text-xs">
          <span className="font-medium">{claim.label}:</span> {claim.text}
        </p>
      ) : null}
      {url && !isSnapshot(source) ? (
        <iframe
          key={url}
          src={url}
          title={`${source.title}, page ${page}`}
          className="h-[36rem] w-full rounded-md border bg-muted"
        />
      ) : (
        <SnapshotView
          url={isSnapshot(source) ? source.raw_url : null}
          quote={claim?.quote ?? null}
        />
      )}
      {source.url ? (
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
        >
          Open the original
        </a>
      ) : null}
    </div>
  );
}

/** The selected source: highlighted PDF at the page, or the web snapshot. */
export function PdfViewer() {
  const { load } = useWorkspace();
  const { selection, selectSource } = useEvidenceSelection();
  if (load.status !== 'ready') return null;
  const value = selection.kind === 'none' ? '' : (selection.sourceId ?? '');
  return (
    <section aria-labelledby="pdf-viewer-title" className="flex flex-col gap-3">
      <h2 id="pdf-viewer-title" className="text-base font-semibold">
        Source viewer
      </h2>
      <SourceSwitcher
        state={load.state}
        value={value}
        onChange={(sourceId) => selectSource(sourceId)}
      />
      <SourceBody state={load.state} />
    </section>
  );
}
