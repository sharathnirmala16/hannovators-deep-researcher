import { useMemo, useState } from 'react';

import type { SourceView } from '@/domains/workspace';
import type { SegmentOption } from '@/shared/ui/segmented';

import {
  matchesFilter,
  sortSources,
  type Sort,
  type SortKey,
  type StatusFilter,
} from './sources';

const FILTERS: readonly { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'kept', label: 'Kept' },
  { value: 'removed', label: 'Removed' },
  { value: 'seeds', label: 'Seeds' },
];

/** Sort and status filter state for the source table, and the visible rows. */
export function useSourceRows(sources: readonly SourceView[]) {
  const [sort, setSort] = useState<Sort>({ key: 'level', direction: 'asc' });
  const [filter, setFilter] = useState<StatusFilter>('all');
  const rows = useMemo(
    () =>
      sortSources(
        sources.filter((source) => matchesFilter(source, filter)),
        sort,
      ),
    [sources, sort, filter],
  );
  const options: SegmentOption<StatusFilter>[] = FILTERS.map((option) => ({
    ...option,
    count: sources.filter((source) => matchesFilter(source, option.value))
      .length,
  }));
  const onSort = (key: SortKey) =>
    setSort((current) => ({
      key,
      direction:
        current.key === key && current.direction === 'asc' ? 'desc' : 'asc',
    }));
  return { rows, sort, onSort, filter, setFilter, options };
}
