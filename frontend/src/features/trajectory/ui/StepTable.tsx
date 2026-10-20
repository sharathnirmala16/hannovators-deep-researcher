import {
  useRef,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from 'react';

import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { TableBody } from '@/shared/ui/table';

import { moveCursor } from '../model/keyboard';
import type { TimeRange } from '../model/timing';
import { useEndPaging } from '../model/useEndPaging';
import { useRowWindow } from '../model/useRowWindow';
import { HEADER_HEIGHT, ROW_HEIGHT, stepRowId } from './columns';
import { StepRow } from './StepRow';
import { StepTableHead } from './StepTableHead';
import { PagingFooter, type PagingState } from './PagingFooter';

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

/** The windowed, keyboard-driven step grid; only its body scrolls. */
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
  const pageNearEnd = useEndPaging(scrollRef, rows.length, paging, ROW_HEIGHT);
  const onScroll = () => {
    view.onScroll();
    pageNearEnd();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTableElement>) => {
    if (event.key === 'Escape' && openId !== null) {
      event.preventDefault();
      onClose();
      return;
    }
    const index = rows.findIndex((step) => step.id === cursorId);
    if ((event.key === 'Enter' || event.key === ' ') && cursorId !== null) {
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
      className="@container scroll-y h-full min-h-0 bg-background"
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
        className={cn(
          'group/grid w-full table-fixed text-xs',
          cursorId === null ? '-outline-offset-2' : 'outline-none',
        )}
      >
        <StepTableHead />
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
          {view.padBottom > 0 ? (
            <tr aria-hidden style={{ height: view.padBottom }} />
          ) : null}
        </TableBody>
      </table>
      {rows.length === 0 ? <div className="p-4">{empty}</div> : null}
      <PagingFooter paging={paging} />
    </div>
  );
}
