import {
  SEARCH_INTENT,
  type SearchIntent,
  type SourceView,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { EmptyState } from '@/shared/ui/states';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';
import { ToneDot, type Tone } from '@/shared/ui/tag';

import { intentCounts } from '../model/funnel';

const INTENT_TONE: Record<SearchIntent, Tone> = {
  CORE: 'info',
  NEGATIVE: 'negative',
  ALTERNATIVE: 'null',
  SAFETY: 'caution',
  SEED_CITATION: 'neutral',
  DEEP_RESEARCH: 'positive',
};

const SEGMENT: Record<Tone, string> = {
  positive: 'bg-tone-positive',
  negative: 'bg-tone-negative',
  caution: 'bg-tone-caution',
  info: 'bg-tone-info',
  null: 'bg-tone-null',
  neutral: 'bg-tone-neutral',
};

const EDGE = 'px-0 first:pl-0 last:pr-0';

/** Sources found and kept per search intent (core, negative, ...). */
export function SearchIntents({ sources }: { sources: readonly SourceView[] }) {
  const counts = intentCounts(sources);
  const total = counts.reduce((sum, item) => sum + item.found, 0);
  if (counts.length === 0) {
    return (
      <EmptyState title="Search intents were not recorded">
        The sources of this run do not say which search found them (core,
        negative, alternative, or safety). Start a new run to see the split.
      </EmptyState>
    );
  }
  if (total === 0) {
    return (
      <EmptyState title="No searches yet">
        Counts per search intent appear here after the search stage.
      </EmptyState>
    );
  }
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <span
        aria-hidden
        className="flex h-1.5 w-full gap-px overflow-hidden rounded-[3px]"
      >
        {counts.map(({ intent, found }) =>
          found > 0 ? (
            <span
              key={intent}
              className={cn('h-full', SEGMENT[INTENT_TONE[intent]])}
              style={{ width: `${(found / total) * 100}%` }}
            />
          ) : null,
        )}
      </span>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className={EDGE}>Search intent</TableHead>
            <TableHead className={cn(EDGE, 'w-14 text-right')}>Found</TableHead>
            <TableHead className={cn(EDGE, 'w-14 text-right')}>Kept</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {counts.map(({ intent, found, kept }) => (
            <TableRow
              key={intent}
              title={SEARCH_INTENT[intent].hint}
              className="hover:bg-transparent"
            >
              <TableCell className={cn(EDGE, 'py-1.5')}>
                <span className="flex min-w-0 items-center gap-2">
                  <ToneDot tone={INTENT_TONE[intent]} />
                  <span className="truncate">
                    {SEARCH_INTENT[intent].label}
                  </span>
                </span>
              </TableCell>
              <TableCell
                className={cn(
                  EDGE,
                  'py-1.5 text-right',
                  found === 0 ? 'text-tone-caution' : 'text-foreground',
                )}
                title={found === 0 ? 'This search found no sources' : undefined}
              >
                {found}
              </TableCell>
              <TableCell
                className={cn(
                  EDGE,
                  'py-1.5 text-right font-semibold',
                  kept > 0 ? 'text-tone-positive' : 'text-muted-foreground',
                )}
              >
                {kept}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
