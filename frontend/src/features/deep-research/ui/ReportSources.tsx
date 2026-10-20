import type { DeepResearchRecord } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

type ReportSource = DeepResearchRecord['sources'][number];

interface ReportSourcesProps {
  sources: readonly ReportSource[];
  active: number | null;
  onOpen: (n: number, source: ReportSource) => void;
}

/** The numbered sources of the report: title, and the URL as a link. */
export function ReportSources({ sources, active, onOpen }: ReportSourcesProps) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <h4 className="text-xs font-medium text-muted-foreground">Sources</h4>
      <ol className="flex min-w-0 flex-col gap-1.5" aria-label="Report sources">
        {sources.map((source, index) => {
          const n = index + 1;
          return (
            <li
              key={`${source.url}-${index}`}
              className="grid min-w-0 grid-cols-[1.5rem_minmax(0,1fr)] gap-x-1.5"
            >
              <span
                className={cn(
                  'justify-self-end text-xs text-muted-foreground tabular-nums',
                  active === n && 'marked font-semibold',
                )}
              >
                {n}
              </span>
              <span className="flex min-w-0 flex-col">
                {source.title ? (
                  <span
                    className="truncate text-xs text-foreground"
                    title={source.title}
                  >
                    {source.title}
                  </span>
                ) : null}
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => onOpen(n, source)}
                  className="truncate font-mono text-xs text-link hover:underline"
                  title={source.url}
                >
                  {source.url}
                </a>
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
