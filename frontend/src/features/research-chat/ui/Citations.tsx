import type { ReactNode } from 'react';

import type { Citation } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

const FOCUS =
  'outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background';

function describe(citation: Citation): string {
  const page = citation.page ? `, page ${citation.page}` : '';
  return `${citation.source_title}${page}`;
}

interface CitationButtonProps {
  n: number;
  citation: Citation | undefined;
  active: boolean;
  onSelect: (citation: Citation) => void;
}

/** An inline `[n]` marker: opens the cited span in the source viewer. */
export function CitationButton({
  n,
  citation,
  active,
  onSelect,
}: CitationButtonProps) {
  if (!citation) {
    return <span className="text-muted-foreground">[{n}]</span>;
  }
  return (
    <button
      type="button"
      aria-pressed={active}
      aria-label={`Citation ${n}: ${describe(citation)}`}
      title={describe(citation)}
      onClick={() => onSelect(citation)}
      className={cn(
        'mx-0.5 inline-flex h-[1.25em] min-w-[1.5em] items-center justify-center rounded-sm px-1 align-baseline font-mono text-xs leading-none font-medium tabular-nums transition-colors',
        active
          ? 'bg-marker text-foreground ring-1 ring-marker-ink'
          : 'bg-muted text-foreground hover:bg-marker',
        FOCUS,
      )}
    >
      {n}
    </button>
  );
}

interface SourceListProps {
  citations: readonly Citation[];
  isActive: (n: number) => boolean;
  onSelect: (citation: Citation) => void;
}

/** The answer's sources, one compact button per citation number. */
export function SourceList({
  citations,
  isActive,
  onSelect,
}: SourceListProps): ReactNode {
  const unique = [
    ...new Map(citations.map((item) => [item.n, item])).values(),
  ].sort((a, b) => a.n - b.n);
  if (unique.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs font-medium text-muted-foreground">Sources</p>
      <ol className="flex flex-col gap-0.5">
        {unique.map((citation) => (
          <li key={citation.n}>
            <button
              type="button"
              aria-pressed={isActive(citation.n)}
              onClick={() => onSelect(citation)}
              className={cn(
                'flex w-full items-baseline gap-2 rounded-sm px-1.5 py-1 text-left text-xs transition-colors',
                isActive(citation.n)
                  ? 'bg-marker text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                FOCUS,
              )}
            >
              <span className="font-mono font-medium tabular-nums text-foreground">
                [{citation.n}]
              </span>
              <span className="min-w-0 flex-1 truncate">
                {citation.source_title}
              </span>
              {citation.page ? (
                <span className="shrink-0 tabular-nums">
                  p. {citation.page}
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
