import { memo } from 'react';

import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { TableCell, TableRow } from '@/shared/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip';

import {
  formatDuration,
  formatOffset,
  formatPercent,
  offsetMs,
  type TimeRange,
} from '../model/timing';
import { ACTOR_LABEL } from '../model/vocabulary';
import { COLUMN, stepRowId } from './columns';
import { KindBadge } from './KindBadge';
import { OutcomeBadge } from './OutcomeBadge';
import { StatusLabel } from './StatusLabel';
import { WaterfallBar } from './WaterfallBar';

interface StepRowProps {
  step: TrajectoryStepSummary;
  origin: number;
  range: TimeRange | null;
  active: boolean;
  open: boolean;
  onSelect: (id: number) => void;
}

const CELL = 'h-7 overflow-hidden px-2 py-0 text-xs';

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
      data-state={open ? 'selected' : undefined}
      data-active={active || undefined}
      onClick={() => onSelect(step.id)}
      className={cn(
        'cursor-default border-b-0 hover:bg-muted',
        'data-[active]:bg-muted group-focus-visible/grid:data-[active]:outline-2 group-focus-visible/grid:data-[active]:-outline-offset-2 group-focus-visible/grid:data-[active]:outline-ring',
      )}
    >
      <TableCell
        className={cn(CELL, COLUMN.index, 'text-muted-foreground tabular-nums')}
      >
        {step.id}
      </TableCell>
      <TableCell
        className={cn(CELL, COLUMN.time, 'text-muted-foreground tabular-nums')}
      >
        {formatOffset(offsetMs(step, origin))}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.actor, 'text-muted-foreground')}>
        {ACTOR_LABEL[step.actor]}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.kind)}>
        <KindBadge kind={step.kind} />
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.name, 'truncate font-medium')}>
        {step.name}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.target)}>
        <TargetText target={step.target} />
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.status)}>
        <StatusLabel status={step.status} />
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.outcome)}>
        {step.outcome ? <OutcomeBadge outcome={step.outcome} /> : null}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.confidence, 'tabular-nums')}>
        {formatPercent(step.confidence)}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.duration, 'tabular-nums')}>
        {formatDuration(step.duration_ms)}
      </TableCell>
      <TableCell className={cn(CELL, COLUMN.waterfall)}>
        {range ? <WaterfallBar step={step} range={range} /> : null}
      </TableCell>
    </TableRow>
  );
});

function TargetText({ target }: { target: string | null }) {
  if (!target) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="block truncate font-mono text-[12px] text-muted-foreground">
          {target}
        </span>
      </TooltipTrigger>
      <TooltipContent
        side="bottom"
        align="start"
        className="max-w-xl font-mono break-all"
      >
        {target}
      </TooltipContent>
    </Tooltip>
  );
}
