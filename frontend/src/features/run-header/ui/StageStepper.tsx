import {
  STAGES,
  STAGE_LABEL,
  type StageId,
  type StageState,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

const SEGMENT: Record<StageState, string> = {
  done: 'bg-foreground',
  active: 'bg-tone-info animate-pulse',
  review: 'bg-tone-caution',
  failed: 'bg-tone-negative',
  pending: 'bg-shade-3',
};

const STATE_TEXT: Record<StageState, string> = {
  done: 'done',
  active: 'running',
  review: 'waiting for review',
  failed: 'failed',
  pending: 'not started',
};

interface StageStepperProps {
  states: Record<StageId, StageState>;
}

function focusStage(states: Record<StageId, StageState>): StageId | null {
  return (
    STAGES.find((stage) => states[stage] === 'failed') ??
    STAGES.find((stage) => states[stage] === 'active') ??
    STAGES.find((stage) => states[stage] === 'review') ??
    null
  );
}

/** The nine stages as one segmented bar, plus the stage in focus. */
export function StageStepper({ states }: StageStepperProps) {
  const focus = focusStage(states);
  const done = STAGES.filter((stage) => states[stage] === 'done').length;
  return (
    <div className="flex items-center gap-2">
      <ol aria-label="Pipeline stages" className="flex items-center gap-[3px]">
        {STAGES.map((stage) => (
          <li
            key={stage}
            title={`${STAGE_LABEL[stage]}: ${STATE_TEXT[states[stage]]}`}
            className={cn('h-1 w-3.5 rounded-full', SEGMENT[states[stage]])}
          >
            <span className="sr-only">
              {STAGE_LABEL[stage]}: {STATE_TEXT[states[stage]]}
            </span>
          </li>
        ))}
      </ol>
      <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">
        {focus ? STAGE_LABEL[focus] : `${done} of ${STAGES.length}`}
      </span>
    </div>
  );
}
