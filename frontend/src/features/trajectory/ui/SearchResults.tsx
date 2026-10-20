import { ExternalLink } from 'lucide-react';

import { SectionHeader } from '@/shared/ui/section-header';

import { searchView } from '../model/bodies';
import type { JsonRecord } from '../model/json';
import { formatCount } from '../model/timing';
import { FactList } from './FactList';

interface SearchResultsProps {
  request: JsonRecord;
  response: JsonRecord;
}

/** Search hits as titles and URLs; links open in a new tab. */
export function SearchResults({ request, response }: SearchResultsProps) {
  const view = searchView(request, response);
  return (
    <section className="flex flex-col gap-3">
      <FactList
        facts={[
          { label: 'Query', value: view.query },
          { label: 'Provider', value: view.provider },
          {
            label: 'Hits',
            value: view.hitCount === null ? null : formatCount(view.hitCount),
          },
        ]}
      />
      {view.hits.length > 0 ? (
        <>
          <SectionHeader
            title="Results"
            meta={<span>{formatCount(view.hits.length)}</span>}
          />
          <ol className="flex flex-col gap-3">
            {view.hits.map((hit, index) => (
              <li
                key={`${index}-${hit.url ?? hit.title}`}
                className="flex gap-2 text-sm"
              >
                <span className="w-6 shrink-0 text-right text-xs leading-5 text-muted-foreground tabular-nums">
                  {index + 1}
                </span>
                <div className="flex min-w-0 max-w-prose flex-col gap-0.5">
                  <span className="font-medium text-foreground">
                    {hit.title}
                  </span>
                  {hit.url ? (
                    <a
                      href={hit.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 rounded-sm font-mono text-xs break-all text-link underline-offset-2 hover:underline"
                    >
                      {hit.url}
                      <ExternalLink aria-hidden className="size-3 shrink-0" />
                      <span className="sr-only">(opens in a new tab)</span>
                    </a>
                  ) : null}
                  {hit.snippet ? (
                    <span className="line-clamp-2 text-xs text-muted-foreground">
                      {hit.snippet}
                    </span>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </>
      ) : null}
    </section>
  );
}
