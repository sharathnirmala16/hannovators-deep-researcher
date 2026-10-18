import { FileText } from 'lucide-react';

import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import {
  formatDuration,
  formatOffset,
  formatPercent,
  offsetMs,
} from '../model/timing';
import { ACTOR_LABEL, STAGE_LABEL } from '../model/vocabulary';
import { FactList } from './FactList';
import { OutcomeBadge } from './OutcomeBadge';
import { SectionTitle } from './SectionTitle';
import { StatusLabel } from './StatusLabel';
import { FOCUS_RING } from './statusStyles';
import type { StepContext } from './stepContext';
import { TargetValue } from './TargetValue';

interface OverviewTabProps {
  step: TrajectoryStepSummary;
  context: StepContext;
}

export function OverviewTab({ step, context }: OverviewTabProps) {
  const parent = step.parent_id;
  return (
    <div className="flex flex-col gap-4">
      {step.summary ? (
        <p className="max-w-prose text-sm leading-relaxed">{step.summary}</p>
      ) : null}
      {step.error ? (
        <pre className="rounded-md bg-shade-2 px-3 py-2 font-mono text-xs whitespace-pre-wrap text-tone-negative">
          {step.error}
        </pre>
      ) : null}
      <FactList
        facts={[
          { label: 'Status', value: <StatusLabel status={step.status} /> },
          {
            label: 'Outcome',
            value: step.outcome ? (
              <OutcomeBadge outcome={step.outcome} />
            ) : null,
          },
          { label: 'Confidence', value: formatPercent(step.confidence) },
          { label: 'Actor', value: ACTOR_LABEL[step.actor] },
          {
            label: 'Stage',
            value: step.stage ? STAGE_LABEL[step.stage] : null,
          },
          { label: 'Target', value: <TargetValue target={step.target} /> },
          {
            label: 'Started',
            value: `${formatOffset(offsetMs(step, context.origin))} after the first step`,
          },
          { label: 'Duration', value: formatDuration(step.duration_ms) },
          {
            label: 'Parent',
            value:
              parent === null ? null : (
                <button
                  type="button"
                  onClick={() => context.onOpenStep(parent)}
                  className={cn(
                    'underline-offset-2 hover:underline',
                    FOCUS_RING,
                  )}
                >
                  #{parent} {context.byId.get(parent)?.name ?? ''}
                </button>
              ),
          },
        ]}
      />
      <LinkedSources step={step} context={context} />
    </div>
  );
}

function LinkedSources({ step, context }: OverviewTabProps) {
  if (step.source_ids.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <SectionTitle
        title="Linked sources"
        meta={String(step.source_ids.length)}
      />
      <p className="text-xs text-muted-foreground">
        Select a source to open it in the Research tab.
      </p>
      <ul className="flex flex-col gap-1">
        {step.source_ids.map((sourceId) => {
          const title = context.sourceTitle(sourceId);
          return (
            <li key={sourceId}>
              <button
                type="button"
                onClick={() => context.onOpenSource(sourceId, step)}
                className={cn(
                  'flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-muted',
                  FOCUS_RING,
                )}
              >
                <FileText
                  aria-hidden
                  className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"
                />
                <span
                  className={cn(
                    'min-w-0',
                    !title && 'font-mono text-xs break-all',
                  )}
                >
                  {title ?? sourceId}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
