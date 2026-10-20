import { memo } from 'react';

import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { TableCell, TableRow } from '@/shared/ui/table';

import {
  formatDuration,
  formatOffset,
  formatPercent,
  offsetMs,
  type TimeRange,
} from '../model/timing';
import { ACTOR_LABEL } from '../model/vocabulary';
import { COLUMN, HAIRLINE, stepRowId } from './columns';
import { KindBadge } from './KindBadge';
import { OutcomeTag } from './OutcomeTag';
import { StatusTag } from './StatusTag';
import { WaterfallBar } from './WaterfallBar';

interface StepRowProps {
  step: TrajectoryStepSummary;
  origin: number;
  range: TimeRange | null;
  active: boolean;
  open: boolean;
  onSelect: (id: number) => void;
}

const CELL = cn('h-8 overflow-hidden px-2 py-0 text-xs', HAIRLINE);
const NUMBER = 'tabular-nums';

/** Row wash: the open row is selected, error rows carry the negative tint. */
function rowClass(step: TrajectoryStepSummary, active: boolean, open: boolean) {
  if (open) {
    return 'bg-accent hover:bg-accent [&>td:first-child]:shadow-[inset_2px_0_0_#18223a,inset_0_-1px_0_var(--color-border)]';
  }
  if (step.status === 'ERROR') {
    return 'bg-tone-negative-tint hover:bg-tone-negative-tint';
  }
  return active ? 'bg-shade-0 hover:bg-shade-0' : 'hover:bg-shade-0';
}

/** One trajectory row. Memoized: stream updates re-render changed rows only. */
export const StepRow = memo(function StepRow({
  step,
  origin,
  range,
  active,
  open,
  onSelect,
}: StepRowProps) {
  return (
    <TableRow
      id={stepRowId(step.id)}
      aria-selected={open}
      data-active={active || undefined}
      onClick={() => onSelect(step.id)}
      className={cn(
        'cursor-default border-b-0',
        rowClass(step, active, open),
        'group-focus-visible/grid:data-[active]:outline-2 group-focus-visible/grid:data-[active]:-outline-offset-2 group-focus-visible/grid:data-[active]:outline-ring',
      )}
    >
      <TableCell
        className={cn(CELL, COLUMN.index, NUMBER, 'text-muted-foreground')}
      >
        {step.id}
      </TableCell>
      <TableCell
        className={cn(CELL, COLUMN.time, NUMBER, 'text-muted-foreground')}
      >
        {formatOffset(offsetMs(step, origin))}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.actor, 'text-muted-foreground')}>
        {ACTOR_LABEL[step.actor]}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.kind)}>
        <KindBadge kind={step.kind} />
      </TableCell>
      <TableCell
        title={step.name}
        className={cn(CELL, COLUMN.name, 'truncate text-sm text-foreground')}
      >
        {step.name}
      </TableCell>
      <TableCell
        title={step.target ?? undefined}
        className={cn(
          CELL,
          COLUMN.target,
          'truncate font-mono text-muted-foreground',
        )}
      >
        {step.target}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.status)}>
        <StatusTag status={step.status} quiet />
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.outcome)}>
        {step.outcome ? <OutcomeTag outcome={step.outcome} /> : null}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.confidence, NUMBER)}>
        {formatPercent(step.confidence)}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.duration, NUMBER)}>
        {formatDuration(step.duration_ms)}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.waterfall)}>
        {range ? <WaterfallBar step={step} range={range} /> : null}
      </TableCell>
    </TableRow>
  );
});
