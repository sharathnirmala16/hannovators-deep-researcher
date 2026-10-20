import type { TrajectoryStepSummary } from '@/domains/workspace';

import {
  formatDuration,
  formatOffset,
  formatPercent,
  offsetMs,
} from '../model/timing';
import { ACTOR_LABEL, STAGE_LABEL } from '../model/vocabulary';
import { FactList } from './FactList';
import { LinkedSources } from './LinkedSources';
import { OutcomeTag } from './OutcomeTag';
import { StatusTag } from './StatusTag';
import type { StepContext } from '../model/stepContext';
import { TargetValue } from './TargetValue';

interface OverviewTabProps {
  step: TrajectoryStepSummary;
  context: StepContext;
}

/** Summary, error, the step's facts, and the sources it touched. */
export function OverviewTab({ step, context }: OverviewTabProps) {
  const parent = step.parent_id;
  return (
    <div className="flex flex-col gap-6">
      {step.summary ? (
        <p className="max-w-prose text-base text-foreground">{step.summary}</p>
      ) : null}
      {step.error ? (
        <pre className="rounded-md bg-tone-negative-tint px-3 py-2 font-mono text-xs leading-5 break-words whitespace-pre-wrap text-tone-negative">
          {step.error}
        </pre>
      ) : null}
      <FactList
        facts={[
          { label: 'Status', value: <StatusTag status={step.status} /> },
          {
            label: 'Outcome',
            value: step.outcome ? <OutcomeTag outcome={step.outcome} /> : null,
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
            // No origin while no row is loaded (every row filtered out).
            value:
              context.steps.length === 0
                ? null
                : `${formatOffset(offsetMs(step, context.origin))} after the first step`,
          },
          { label: 'Duration', value: formatDuration(step.duration_ms) },
          {
            label: 'Parent',
            value:
              parent === null ? null : (
                <button
                  type="button"
                  onClick={() => context.onOpenStep(parent)}
                  className="rounded-sm text-left text-link underline-offset-2 hover:underline"
                >
                  Step {parent} {context.byId.get(parent)?.name ?? ''}
                </button>
              ),
          },
        ]}
      />
      <LinkedSources step={step} context={context} />
    </div>
  );
}
