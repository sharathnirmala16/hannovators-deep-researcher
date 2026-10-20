import { cn } from '@/shared/lib/cn';
import { TableHead, TableHeader, TableRow } from '@/shared/ui/table';

import { COLUMN, HAIRLINE, HEADERS, HEADER_HEIGHT } from './columns';

/** Sticky header of the step table: graphite sentence-case labels. */
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
              'sticky top-0 z-10 bg-background px-2 text-xs font-medium text-muted-foreground',
              HAIRLINE,
            )}
          >
            {label}
          </TableHead>
        ))}
      </TableRow>
    </TableHeader>
  );
}
