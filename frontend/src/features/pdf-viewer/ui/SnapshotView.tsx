import { useEffect, useMemo, useRef, useState } from 'react';

import { parseMarkdown, textRuns } from '@/shared/lib/markdown';
import { MarkdownBlocks } from '@/shared/ui/markdown';

import { fetchSnapshot } from '../api/fetchSnapshot';
import { markQuote } from '../model/markQuote';

type SnapshotLoad =
  | { url: string; status: 'ready'; text: string }
  | { url: string; status: 'error'; message: string };

interface SnapshotViewProps {
  url: string | null;
  quote: string | null;
}

function Marked({ text, quote }: { text: string; quote: string | null }) {
  return (
    <>
      {markQuote(text, quote).map((segment, index) =>
        segment.marked ? (
          <mark
            key={index}
            className="rounded-sm bg-marker px-0.5 text-foreground"
          >
            {segment.text}
          </mark>
        ) : (
          <span key={index}>{segment.text}</span>
        ),
      )}
    </>
  );
}

function QuoteCallout({ quote }: { quote: string }) {
  return (
    <blockquote className="border-l-2 border-marker-ink pl-3 font-serif leading-relaxed">
      <mark className="rounded-sm bg-marker px-0.5 text-foreground">
        {quote}
      </mark>
    </blockquote>
  );
}

/** The snapshot rendered as markdown, with the quote marked where it appears. */
function SnapshotDocument({
  text,
  quote,
}: {
  text: string;
  quote: string | null;
}) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  const found = useMemo(
    () =>
      !quote ||
      textRuns(blocks).some((run) =>
        markQuote(run, quote).some((segment) => segment.marked),
      ),
    [blocks, quote],
  );
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector('mark')?.scrollIntoView?.({ block: 'center' });
  }, [blocks, quote]);

  return (
    <div ref={ref} className="flex min-w-0 flex-col gap-4">
      {found || !quote ? null : (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">
            The quoted passage, not found word for word in the page:
          </p>
          <QuoteCallout quote={quote} />
        </div>
      )}
      <MarkdownBlocks
        blocks={blocks}
        className="reading text-sm leading-6 text-foreground"
        text={(run) => <Marked text={run} quote={quote} />}
      />
    </div>
  );
}

/** Web source: the saved snapshot as markdown with the claim's quote marked. */
export function SnapshotView({ url, quote }: SnapshotViewProps) {
  const [load, setLoad] = useState<SnapshotLoad | null>(null);

  useEffect(() => {
    if (!url) return undefined;
    const controller = new AbortController();
    fetchSnapshot(url, controller.signal).then(
      (text) => setLoad({ url, status: 'ready', text }),
      (error: unknown) => {
        if (controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : String(error);
        setLoad({ url, status: 'error', message });
      },
    );
    return () => controller.abort();
  }, [url]);

  const current = load && load.url === url ? load : null;
  const problem =
    current?.status === 'error'
      ? current.message
      : 'The snapshot file is not available.';
  if (current?.status === 'ready') {
    return <SnapshotDocument text={current.text} quote={quote} />;
  }
  return (
    <div className="space-y-2 rounded-md bg-muted p-4 text-sm">
      <p className="text-xs text-muted-foreground">
        {url && !current
          ? 'Loading the snapshot.'
          : `${problem} Only the extracted quote is shown.`}
      </p>
      {quote ? <QuoteCallout quote={quote} /> : null}
    </div>
  );
}
