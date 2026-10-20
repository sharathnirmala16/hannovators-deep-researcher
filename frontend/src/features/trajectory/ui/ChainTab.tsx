import type { TrajectoryStepSummary } from '@/domains/workspace';
import { SectionHeader } from '@/shared/ui/section-header';

import { ancestorIds, childrenOf } from '../model/steps';
import { ChainEntry } from './ChainEntry';
import type { StepContext } from '../model/stepContext';
import { StepLink } from './StepLink';

interface ChainTabProps {
  step: TrajectoryStepSummary;
  context: StepContext;
}

/** Parent chain from the root down to this step, then its children. */
export function ChainTab({ step, context }: ChainTabProps) {
  const ancestors = ancestorIds(context.byId, step);
  const children = childrenOf(context.steps, step.id);
  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-2">
        <SectionHeader title="Parents" meta={<span>{ancestors.length}</span>} />
        {ancestors.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            This is a top-level step.
          </p>
        ) : null}
        <ol className="flex flex-col">
          {ancestors.map((id, depth) => (
            <li key={id} style={{ paddingLeft: depth * 16 }}>
              <ChainEntry id={id} context={context} />
            </li>
          ))}
          <li style={{ paddingLeft: ancestors.length * 16 }}>
            <StepLink step={step} onOpen={context.onOpenStep} current />
          </li>
        </ol>
      </section>
      <section className="flex flex-col gap-2">
        <SectionHeader title="Children" meta={<span>{children.length}</span>} />
        {children.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No loaded step has this step as its parent.
          </p>
        ) : (
          <ul className="flex flex-col">
            {children.map((child) => (
              <li key={child.id}>
                <StepLink step={child} onOpen={context.onOpenStep} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
