import { useWorkspace, type WorkspaceState } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { plural } from '@/shared/lib/format';
import { SectionHeader } from '@/shared/ui/section-header';

import { funnelSteps, rejectionCounts } from '../model/funnel';
import { SearchIntents } from './SearchIntents';

function Bar({
  value,
  max,
  strong,
}: {
  value: number;
  max: number;
  strong: boolean;
}) {
  const width = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <span aria-hidden className="block h-1.5 w-full rounded-full bg-shade-2">
      <span
        className={cn(
          'block h-full rounded-full',
          strong ? 'bg-shade-6' : 'bg-shade-4',
        )}
        style={{ width: `${width}%` }}
      />
    </span>
  );
}

function Flow({ state }: { state: WorkspaceState }) {
  const steps = funnelSteps(state.funnel);
  const max = steps[0]?.count ?? 0;
  return (
    <ol aria-label="Screening flow" className="flex flex-col gap-2">
      {state.funnel.seeds > 0 ? (
        <li className="text-xs text-muted-foreground">
          Plus {plural(state.funnel.seeds, 'seed')} you provided
        </li>
      ) : null}
      {steps.map((step, index) => (
        <li key={step.id} className="flex flex-col gap-1">
          <div className="flex items-baseline gap-2 text-sm">
            <span>{step.label}</span>
            {step.removed && step.removed.count > 0 ? (
              <span className="text-xs text-tone-negative tabular-nums">
                {step.removed.count} {step.removed.label}
              </span>
            ) : null}
            <span className="ml-auto font-medium tabular-nums">
              {step.count}
            </span>
          </div>
          <Bar
            value={step.count}
            max={max}
            strong={index === steps.length - 1}
          />
        </li>
      ))}
    </ol>
  );
}

function Reasons({ state }: { state: WorkspaceState }) {
  const reasons = rejectionCounts(state.sources);
  if (reasons.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-xs font-medium text-muted-foreground">
        Why sources were removed
      </h4>
      <ul className="flex flex-col">
        {reasons.map((reason) => (
          <li key={reason.code} className="flex items-baseline gap-2 text-xs">
            <span>{reason.label}</span>
            <span className="ml-auto text-muted-foreground tabular-nums">
              {reason.count}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** PRISMA-style funnel, search intents, and removal reasons. */
export function ScreeningFunnel() {
  const { load } = useWorkspace();
  if (load.status !== 'ready') return null;
  const { state } = load;
  return (
    <section aria-labelledby="funnel-title" className="flex flex-col gap-4">
      <SectionHeader
        id="funnel-title"
        title="Screening"
        meta={<span>{plural(state.sources.length, 'source')}</span>}
      />
      {state.sources.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          The funnel fills in as the search finds sources.
        </p>
      ) : (
        <>
          <Flow state={state} />
          <SearchIntents sources={state.sources} />
          <Reasons state={state} />
        </>
      )}
    </section>
  );
}
