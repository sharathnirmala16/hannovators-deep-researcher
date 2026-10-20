import type { TrajectoryStepSummary } from '@/domains/workspace';
import { SectionHeader } from '@/shared/ui/section-header';

import { childrenOf } from '../model/steps';
import {
  formatClock,
  formatDuration,
  formatOffset,
  offsetMs,
  timeRange,
} from '../model/timing';
import { FactList } from './FactList';
import type { StepContext } from '../model/stepContext';
import { StepLink } from './StepLink';
import { WaterfallBar } from './WaterfallBar';

interface TimingTabProps {
  step: TrajectoryStepSummary;
  context: StepContext;
}

function shareOfParent(
  step: TrajectoryStepSummary,
  parent: TrajectoryStepSummary | undefined,
): string | null {
  if (!parent?.duration_ms || step.duration_ms === null) return null;
  const share = Math.round((step.duration_ms / parent.duration_ms) * 100);
  return `${share}% of step ${parent.id} ${parent.name}`;
}

export function TimingTab({ step, context }: TimingTabProps) {
  const parent =
    step.parent_id === null ? undefined : context.byId.get(step.parent_id);
  const children = childrenOf(context.steps, step.id);
  const range = timeRange([step, ...children]);
  return (
    <div className="flex flex-col gap-6">
      <FactList
        facts={[
          { label: 'Started', value: formatClock(step.started_at) },
          {
            label: 'Ended',
            value: step.ended_at ? formatClock(step.ended_at) : 'Still running',
          },
          { label: 'Duration', value: formatDuration(step.duration_ms) },
          {
            label: 'Since first step',
            value:
              context.steps.length === 0
                ? null
                : formatOffset(offsetMs(step, context.origin)),
          },
          { label: 'Share of parent', value: shareOfParent(step, parent) },
        ]}
      />
      {children.length > 0 && range ? (
        <section className="flex flex-col gap-2">
          <SectionHeader
            title="Child steps"
            meta={<span>{children.length}</span>}
          />
          <ul className="flex flex-col">
            {children.map((child) => (
              <li
                key={child.id}
                className="grid grid-cols-[minmax(0,1fr)_8rem_4.5rem] items-center gap-3"
              >
                <StepLink step={child} onOpen={context.onOpenStep} />
                <WaterfallBar step={child} range={range} />
                <span className="text-right text-xs tabular-nums">
                  {formatDuration(child.duration_ms)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
