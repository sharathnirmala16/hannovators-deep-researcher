import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { ancestorIds, childrenOf } from '../model/steps';
import { SectionTitle } from './SectionTitle';
import type { StepContext } from './stepContext';
import { StepLink } from './StepLink';
import { FOCUS_RING } from './statusStyles';

interface ChainTabProps {
  step: TrajectoryStepSummary;
  context: StepContext;
}

/** Parent chain from the root down to this step, then its children. */
export function ChainTab({ step, context }: ChainTabProps) {
  const ancestors = ancestorIds(context.byId, step);
  const children = childrenOf(context.steps, step.id);
  return (
    <div className="flex flex-col gap-4">
      <section className="flex flex-col gap-1">
        <SectionTitle title="Parents" meta={String(ancestors.length)} />
        {ancestors.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            This is a top-level step.
          </p>
        ) : null}
        <ol className="flex flex-col">
          {ancestors.map((id, depth) => (
            <li key={id} style={{ paddingLeft: depth * 12 }}>
              <ChainEntry id={id} context={context} />
            </li>
          ))}
          <li style={{ paddingLeft: ancestors.length * 12 }}>
            <StepLink step={step} onOpen={context.onOpenStep} current />
          </li>
        </ol>
      </section>
      <section className="flex flex-col gap-1">
        <SectionTitle title="Children" meta={String(children.length)} />
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

/** An ancestor; it may sit on a page that is not loaded yet. */
function ChainEntry({ id, context }: { id: number; context: StepContext }) {
  const loaded = context.byId.get(id);
  if (loaded) return <StepLink step={loaded} onOpen={context.onOpenStep} />;
  return (
    <button
      type="button"
      onClick={() => context.onOpenStep(id)}
      className={cn(
        'flex h-7 items-center gap-2 rounded-md px-2 text-xs text-muted-foreground hover:bg-muted',
        FOCUS_RING,
      )}
    >
      #{id} (not loaded yet)
    </button>
  );
}
