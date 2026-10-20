import { studyLabel, type SourceView } from '@/domains/workspace';

function hostOf(url: string | null): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

/** Second line of a source row: first author and year, or the web host; venue. */
export function SourceByline({ source }: { source: SourceView }) {
  const label = studyLabel(source);
  const byline = label === source.title ? null : label;
  const host = byline ? null : hostOf(source.url);
  if (!byline && !host && !source.venue) return null;
  return (
    <div className="flex min-w-0 gap-2 text-xs text-muted-foreground">
      {byline ? <span className="shrink-0">{byline}</span> : null}
      {host ? (
        <span className="truncate font-mono" title={source.url ?? undefined}>
          {host}
        </span>
      ) : null}
      {source.venue ? (
        <span className="truncate" title={source.venue}>
          {source.venue}
        </span>
      ) : null}
    </div>
  );
}
