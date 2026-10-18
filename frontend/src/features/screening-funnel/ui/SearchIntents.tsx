import { SEARCH_INTENT, type SourceView } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { intentCounts } from '../model/funnel';

/** Sources found and kept per search intent (core, negative, ...). */
export function SearchIntents({ sources }: { sources: readonly SourceView[] }) {
  const counts = intentCounts(sources);
  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-xs font-medium text-muted-foreground">
        Search intents
      </h4>
      {counts.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          This run did not record which search found each source.
        </p>
      ) : (
        <table className="w-full text-xs tabular-nums">
          <thead className="sr-only">
            <tr>
              <th>Intent</th>
              <th>Found</th>
              <th>Kept</th>
            </tr>
          </thead>
          <tbody>
            {counts.map(({ intent, found, kept }) => (
              <tr key={intent} title={SEARCH_INTENT[intent].hint}>
                <td className="py-0.5">
                  <span
                    className={cn(
                      found === 0 && 'text-tone-caution',
                      intent === 'NEGATIVE' && found > 0 && 'font-medium',
                    )}
                  >
                    {SEARCH_INTENT[intent].label}
                  </span>
                </td>
                <td className="py-0.5 text-right text-muted-foreground">
                  {found} found
                </td>
                <td className="w-16 py-0.5 text-right">{kept} kept</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
