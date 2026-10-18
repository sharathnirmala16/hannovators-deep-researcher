import { useEffect, useState } from 'react';

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

/** Web source: the saved snapshot text with the claim's quote marked. */
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
  if (current?.status === 'ready') {
    return (
      <div className="max-h-[32rem] overflow-auto rounded-md bg-muted p-4 font-serif text-sm leading-relaxed whitespace-pre-wrap">
        <Marked text={current.text} quote={quote} />
      </div>
    );
  }
  return (
    <div className="space-y-2 rounded-md bg-muted p-4 text-sm">
      <p className="text-xs text-muted-foreground">
        {url && !current
          ? 'Loading the snapshot.'
          : 'The snapshot file is not available, so only the extracted quote is shown.'}
      </p>
      {quote ? (
        <blockquote className="border-l-2 border-marker-ink pl-3 font-serif leading-relaxed">
          <mark className="rounded-sm bg-marker px-0.5 text-foreground">
            {quote}
          </mark>
        </blockquote>
      ) : null}
    </div>
  );
}
