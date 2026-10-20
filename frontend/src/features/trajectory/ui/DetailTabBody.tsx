import type { TrajectoryStepSummary } from '@/domains/workspace';
import { ErrorState, SkeletonBlock } from '@/shared/ui/states';

import type { StepDetail } from '../model/useStepDetail';
import { BodyTab } from './BodyTab';
import { ChainTab } from './ChainTab';
import type { DetailTab } from './detailTabs';
import { OverviewTab } from './OverviewTab';
import type { StepContext } from '../model/stepContext';
import { TimingTab } from './TimingTab';

interface DetailTabBodyProps {
  tab: DetailTab;
  /** Undefined until the step is loaded (it is not among the rows). */
  step: TrajectoryStepSummary | undefined;
  detail: StepDetail;
  context: StepContext;
}

/** The content of the selected detail tab, or the step's load state. */
export function DetailTabBody({
  tab,
  step,
  detail,
  context,
}: DetailTabBodyProps) {
  if (!step) {
    return detail.phase === 'error' || detail.phase === 'unavailable' ? (
      <ErrorState title="Could not load this step" message={detail.message} />
    ) : (
      <SkeletonBlock lines={4} label="Loading the step" />
    );
  }
  switch (tab) {
    case 'overview':
      return <OverviewTab step={step} context={context} />;
    case 'request':
    case 'response':
      return <BodyTab part={tab} detail={detail} />;
    case 'timing':
      return <TimingTab step={step} context={context} />;
    case 'chain':
      return <ChainTab step={step} context={context} />;
  }
}
