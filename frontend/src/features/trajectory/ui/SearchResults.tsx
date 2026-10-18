import { ExternalLink } from 'lucide-react';

import { cn } from '@/shared/lib/cn';

import { searchView } from '../model/bodies';
import type { JsonRecord } from '../model/json';
import { formatCount } from '../model/timing';
import { FactList } from './FactList';
import { SectionTitle } from './SectionTitle';
import { FOCUS_RING } from './statusStyles';

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
          <SectionTitle title="Results" meta={formatCount(view.hits.length)} />
          <ol className="flex flex-col gap-2">
            {view.hits.map((hit, index) => (
              <li
                key={`${index}-${hit.url ?? hit.title}`}
                className="flex gap-2 text-[13px]"
              >
                <span className="w-6 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                  {index + 1}
                </span>
                <div className="flex min-w-0 flex-col gap-0.5">
                  <span className="font-medium">{hit.title}</span>
                  {hit.url ? (
                    <a
                      href={hit.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={cn(
                        'flex items-center gap-1 font-mono text-xs break-all text-muted-foreground underline-offset-2 hover:text-foreground hover:underline',
                        FOCUS_RING,
                      )}
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
