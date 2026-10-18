import { cn } from '@/shared/lib/cn';
import { TableHead, TableHeader, TableRow } from '@/shared/ui/table';

import { COLUMN, HEADER_HEIGHT } from './columns';

const HEADERS: readonly (readonly [keyof typeof COLUMN, string])[] = [
  ['index', '#'],
  ['time', 'Time'],
  ['actor', 'Actor'],
  ['kind', 'Kind'],
  ['name', 'Name'],
  ['target', 'Target'],
  ['status', 'Status'],
  ['outcome', 'Outcome'],
  ['confidence', 'Conf.'],
  ['duration', 'Duration'],
  ['waterfall', 'Waterfall'],
];

/** Sticky header of the step table. */
export function StepTableHead() {
  return (
    <TableHeader className="[&_tr]:border-b-0">
      <TableRow className="hover:bg-transparent">
        {HEADERS.map(([column, label]) => (
          <TableHead
            key={column}
            scope="col"
            style={{ height: HEADER_HEIGHT }}
            className={cn(
              COLUMN[column],
              'sticky top-0 z-10 bg-background px-2 text-xs font-medium text-muted-foreground shadow-[inset_0_-1px_0_var(--color-border)]',
            )}
          >
            {label}
          </TableHead>
        ))}
      </TableRow>
    </TableHeader>
  );
}
