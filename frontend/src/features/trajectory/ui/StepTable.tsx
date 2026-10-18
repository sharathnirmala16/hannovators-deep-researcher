import {
  useEffect,
  useRef,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from 'react';

import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { TableBody, TableHead, TableHeader, TableRow } from '@/shared/ui/table';

import { moveCursor } from '../model/keyboard';
import type { TimeRange } from '../model/timing';
import { useRowWindow } from '../model/useRowWindow';
import {
  COLUMN,
  COLUMN_COUNT,
  HEADER_HEIGHT,
  ROW_HEIGHT,
  stepRowId,
} from './columns';
import { StepRow } from './StepRow';
import { SCROLL_Y } from './statusStyles';
import { TableFooterRow, type PagingState } from './TableFooterRow';

interface StepTableProps {
  rows: readonly TrajectoryStepSummary[];
  origin: number;
  range: TimeRange | null;
  cursorId: number | null;
  openId: number | null;
  onCursor: (id: number, open: boolean) => void;
  onOpen: (id: number) => void;
  onClose: () => void;
  paging: PagingState;
  /** Shown as the only row when no row matches. */
  empty: ReactNode;
  gridRef: RefObject<HTMLTableElement | null>;
}

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

/** Load the next page when the user scrolls within this many rows of the end. */
const END_THRESHOLD_ROWS = 8;

export function StepTable({
  rows,
  origin,
  range,
  cursorId,
  openId,
  onCursor,
  onOpen,
  onClose,
  paging,
  empty,
  gridRef,
}: StepTableProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const view = useRowWindow(scrollRef, rows.length, ROW_HEIGHT, HEADER_HEIGHT);
  const { hasMore, loadingMore, onLoadMore } = paging;

  // Keep paging while the loaded rows do not fill the viewport.
  useEffect(() => {
    const element = scrollRef.current;
    if (!element || !hasMore || loadingMore) return;
    if (element.scrollHeight <= element.clientHeight + ROW_HEIGHT) onLoadMore();
  }, [rows.length, hasMore, loadingMore, onLoadMore]);

  const onScroll = () => {
    view.onScroll();
    const element = scrollRef.current;
    if (!element || !hasMore || loadingMore) return;
    const left =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    if (left < ROW_HEIGHT * END_THRESHOLD_ROWS) onLoadMore();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTableElement>) => {
    if (event.key === 'Escape' && openId !== null) {
      event.preventDefault();
      onClose();
      return;
    }
    const index = rows.findIndex((step) => step.id === cursorId);
    if (event.key === 'Enter' && cursorId !== null) {
      event.preventDefault();
      onOpen(cursorId);
      return;
    }
    const height = scrollRef.current?.clientHeight ?? 0;
    const page = Math.max(1, Math.floor((height - HEADER_HEIGHT) / ROW_HEIGHT));
    const next = moveCursor(event.key, index, rows.length, page);
    const step = next === null ? undefined : rows[next];
    if (next === null || !step) return;
    event.preventDefault();
    view.reveal(next);
    onCursor(step.id, openId !== null);
  };

  const visible = rows.slice(view.start, view.end);
  return (
    <div
      ref={scrollRef}
      onScroll={onScroll}
      className={cn('@container h-full min-h-0', SCROLL_Y)}
    >
      <table
        ref={gridRef}
        role="grid"
        aria-label="Trajectory steps"
        aria-rowcount={rows.length}
        aria-activedescendant={
          cursorId === null ? undefined : stepRowId(cursorId)
        }
        tabIndex={0}
        onKeyDown={onKeyDown}
        className="group/grid w-full table-fixed text-xs outline-none"
      >
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
        <TableBody>
          {view.padTop > 0 ? (
            <tr aria-hidden style={{ height: view.padTop }} />
          ) : null}
          {visible.map((step) => (
            <StepRow
              key={step.id}
              step={step}
              origin={origin}
              range={range}
              active={step.id === cursorId}
              open={step.id === openId}
              onSelect={onOpen}
            />
          ))}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>{empty}</td>
            </tr>
          ) : null}
          {view.padBottom > 0 ? (
            <tr aria-hidden style={{ height: view.padBottom }} />
          ) : null}
          <TableFooterRow paging={paging} columns={COLUMN_COUNT} />
        </TableBody>
      </table>
    </div>
  );
}
