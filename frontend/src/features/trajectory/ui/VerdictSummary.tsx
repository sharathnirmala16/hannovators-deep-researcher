import type { TrajectoryStep } from '@/domains/workspace';

import { verdictView } from '../model/bodies';
import { formatPercent } from '../model/timing';
import { FactList } from './FactList';
import { OutcomeBadge } from './OutcomeBadge';

/** Why a source was kept, removed, or flagged. */
export function VerdictSummary({ step }: { step: TrajectoryStep }) {
  const view = verdictView(step.response);
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        {step.outcome ? (
          <OutcomeBadge outcome={step.outcome} className="text-[13px]" />
        ) : (
          <span className="text-[13px] text-muted-foreground">No outcome</span>
        )}
        {step.confidence !== null ? (
          <span className="text-xs text-muted-foreground tabular-nums">
            Confidence {formatPercent(step.confidence)}
          </span>
        ) : null}
      </div>
      {view.reason ? (
        <p className="max-w-prose text-sm leading-relaxed">{view.reason}</p>
      ) : null}
      <FactList
        facts={view.facts.map((fact) => ({
          label: fact.label,
          value: <span className="tabular-nums">{fact.value}</span>,
        }))}
      />
    </section>
  );
}
