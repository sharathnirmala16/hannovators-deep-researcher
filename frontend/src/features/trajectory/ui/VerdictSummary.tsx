import type { TrajectoryStep } from '@/domains/workspace';

import { verdictView } from '../model/bodies';
import { formatPercent } from '../model/timing';
import { FactList } from './FactList';
import { OutcomeTag } from './OutcomeTag';

/** Why a source was kept, removed, or flagged. */
export function VerdictSummary({ step }: { step: TrajectoryStep }) {
  const view = verdictView(step.response);
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        {step.outcome ? (
          <OutcomeTag outcome={step.outcome} />
        ) : (
          <span className="text-sm text-muted-foreground">No outcome</span>
        )}
        {step.confidence !== null ? (
          <span className="text-xs text-muted-foreground tabular-nums">
            Confidence {formatPercent(step.confidence)}
          </span>
        ) : null}
      </div>
      {view.reason ? (
        <p className="max-w-prose text-base text-foreground">{view.reason}</p>
      ) : null}
      <FactList facts={view.facts} />
    </section>
  );
}
