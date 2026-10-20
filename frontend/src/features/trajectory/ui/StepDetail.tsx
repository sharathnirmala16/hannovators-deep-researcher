import { useState, type KeyboardEvent } from 'react';

import type { TrajectoryStepSummary } from '@/domains/workspace';
import { Segmented } from '@/shared/ui/segmented';

import type { StepDetail as Detail } from '../model/useStepDetail';
import { DetailTabBody } from './DetailTabBody';
import { DETAIL_TABS, type DetailTab } from './detailTabs';
import type { StepContext } from '../model/stepContext';
import { StepDetailHeader } from './StepDetailHeader';

interface StepDetailProps {
  stepId: number;
  summary: TrajectoryStepSummary | undefined;
  detail: Detail;
  context: StepContext;
  onClose: () => void;
}

/** Right-side panel for the open step; its body scrolls on its own. */
export function StepDetail({
  stepId,
  summary,
  detail,
  context,
  onClose,
}: StepDetailProps) {
  // The tab stays put while the user arrows through rows.
  const [tab, setTab] = useState<DetailTab>('overview');
  // The loaded row is the freshest summary (the stream updates it in place).
  const step = summary ?? (detail.phase === 'ready' ? detail.step : undefined);
  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    onClose();
  };
  return (
    <section
      aria-label={`Step ${stepId} details`}
      onKeyDown={onKeyDown}
      className="flex h-full min-h-0 flex-col overflow-hidden bg-background"
    >
      <StepDetailHeader
        stepId={stepId}
        step={step}
        onClose={onClose}
        tabs={
          step ? (
            <Segmented
              label="Step detail view"
              value={tab}
              options={DETAIL_TABS}
              onChange={setTab}
              className="self-start"
            />
          ) : null
        }
      />
      <div className="scroll-y min-h-0 flex-1 p-4">
        <DetailTabBody
          tab={tab}
          step={step}
          detail={detail}
          context={context}
        />
      </div>
    </section>
  );
}
