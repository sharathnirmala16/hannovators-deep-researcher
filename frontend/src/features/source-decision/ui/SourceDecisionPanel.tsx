import { CircleMinusIcon, CirclePlusIcon } from 'lucide-react';

import {
  SOURCE_DECISION,
  SOURCE_STATUS,
  type SourceDecision,
  type SourceView,
} from '@/domains/workspace';
import { absoluteTime, relativeTime } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import { Tag, ToneDot } from '@/shared/ui/tag';

import { DECISION_COPY } from '../model/decision';
import { useDecisionControl } from '../model/useDecisionControl';
import { DecisionDialog } from './DecisionDialog';

/** The researcher's mark: an ink rule, their decision, reason, and status. */
function DecisionRecord({ decision }: { decision: SourceDecision }) {
  const label = SOURCE_DECISION[decision.decision];
  return (
    <div className="flex flex-col gap-1.5 border-l-2 border-ink pl-3">
      <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Tag tone={label.tone}>{label.label}</Tag>
        <time
          dateTime={decision.decided_at}
          title={absoluteTime(decision.decided_at)}
        >
          {relativeTime(decision.decided_at)}
        </time>
      </p>
      {decision.reason ? (
        <p className="reading text-base text-foreground">{decision.reason}</p>
      ) : (
        <p className="text-sm text-muted-foreground">No reason given.</p>
      )}
      <p className="text-xs text-muted-foreground">
        The agent's decision: {SOURCE_STATUS[decision.agent_status].label}.
      </p>
      {decision.applied ? null : (
        <p className="inline-flex items-center gap-1.5 text-xs text-tone-caution">
          <ToneDot tone="caution" />
          Not in the synthesis yet. Re-synthesize from the evidence pane.
        </p>
      )}
    </div>
  );
}

/** Your decision on the source, and the include or exclude action. */
export function SourceDecisionPanel({ source }: { source: SourceView }) {
  const control = useDecisionControl(source);
  if (!control.kind) return null;
  const include = control.kind === 'INCLUDE';
  return (
    <section aria-labelledby="source-decision" className="flex flex-col gap-2">
      <h3
        id="source-decision"
        className="text-xs font-medium text-muted-foreground"
      >
        Your decision
      </h3>
      {source.decision ? <DecisionRecord decision={source.decision} /> : null}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Button
          size="sm"
          variant="outline"
          disabled={control.unavailable !== null}
          onClick={() => control.setOpen(true)}
        >
          {include ? <CirclePlusIcon /> : <CircleMinusIcon />}
          {DECISION_COPY[control.kind].action}
        </Button>
        <span className="text-xs text-muted-foreground">
          {control.unavailable ??
            'Overrides the agent and is recorded in the trajectory.'}
        </span>
      </div>
      <DecisionDialog source={source} control={control} />
    </section>
  );
}
