import { cn } from '@/shared/lib/cn';
import { TableHead, TableHeader, TableRow } from '@/shared/ui/table';

import type { Sort, SortKey } from '../model/sources';
import { SortButton } from './SortButton';

const STICKY = 'sticky top-0 z-10 border-b bg-background';

interface Column {
  keys: readonly { key: SortKey; label: string }[];
  className?: string;
}

/** Cells hold two stacked values, so a header holds their two sort controls. */
const COLUMNS: readonly Column[] = [
  { keys: [{ key: 'title', label: 'Title' }] },
  {
    keys: [
      { key: 'level', label: 'Level' },
      { key: 'intent', label: 'Intent' },
    ],
    className: 'w-[120px]',
  },
  {
    keys: [
      { key: 'status', label: 'Status' },
      { key: 'stance', label: 'Stance' },
    ],
    className: 'w-32',
  },
  {
    keys: [{ key: 'score', label: 'Score' }],
    className: 'w-[70px] text-right',
  },
];

function ariaSort(column: Column, sort: Sort) {
  if (!column.keys.some(({ key }) => key === sort.key)) return undefined;
  return sort.direction === 'asc' ? 'ascending' : 'descending';
}

/** Sticky header row with a sort control per value. */
export function SourceTableHeader({
  sort,
  onSort,
}: {
  sort: Sort;
  onSort: (key: SortKey) => void;
}) {
  return (
    <TableHeader>
      <TableRow>
        {COLUMNS.map((column) => (
          <TableHead
            key={column.keys[0]?.key}
            aria-sort={ariaSort(column, sort)}
            className={cn(STICKY, column.className)}
          >
            <span className="inline-flex items-center gap-2">
              {column.keys.map(({ key, label }) => (
                <SortButton
                  key={key}
                  label={label}
                  sortKey={key}
                  sort={sort}
                  onSort={onSort}
                />
              ))}
            </span>
          </TableHead>
        ))}
      </TableRow>
    </TableHeader>
  );
}
