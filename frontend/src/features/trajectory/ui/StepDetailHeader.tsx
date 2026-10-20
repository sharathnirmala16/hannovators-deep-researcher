import { X } from 'lucide-react';
import type { ReactNode } from 'react';

import type { TrajectoryStepSummary } from '@/domains/workspace';
import { Button } from '@/shared/ui/button';

import { KindBadge } from './KindBadge';
import { OutcomeTag } from './OutcomeTag';
import { StatusTag } from './StatusTag';

interface StepDetailHeaderProps {
  stepId: number;
  step: TrajectoryStepSummary | undefined;
  onClose: () => void;
  /** The tab switcher, on its own line below the title. */
  tabs: ReactNode;
}

/** Step name, kind, status and outcome tags, the close button, and tabs. */
export function StepDetailHeader({
  stepId,
  step,
  onClose,
  tabs,
}: StepDetailHeaderProps) {
  return (
    <header className="flex shrink-0 flex-col gap-2 border-b bg-background px-4 pt-2 pb-3">
      <div className="flex min-h-8 items-center gap-2">
        <h2
          className="min-w-0 flex-1 truncate text-base font-semibold text-foreground"
          title={step?.name}
        >
          {step?.name ?? `Step ${stepId}`}
        </h2>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Close details"
          title="Close (Esc)"
          onClick={onClose}
        >
          <X aria-hidden />
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {step ? <KindBadge kind={step.kind} /> : null}
        <span className="text-xs text-muted-foreground tabular-nums">
          Step {stepId}
        </span>
        {step ? <StatusTag status={step.status} /> : null}
        {step?.outcome ? <OutcomeTag outcome={step.outcome} /> : null}
      </div>
      {tabs}
    </header>
  );
}
