import { X } from 'lucide-react';
import type { KeyboardEvent } from 'react';

import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs';

import type { StepDetail as Detail } from '../model/useStepDetail';
import { BodySkeleton } from './BodySkeleton';
import { BodyTab } from './BodyTab';
import { ChainTab } from './ChainTab';
import { KindBadge } from './KindBadge';
import { Notice } from './Notice';
import { OverviewTab } from './OverviewTab';
import { SCROLL_Y } from './statusStyles';
import type { StepContext } from './stepContext';
import { TimingTab } from './TimingTab';

interface StepDetailProps {
  stepId: number;
  summary: TrajectoryStepSummary | undefined;
  detail: Detail;
  context: StepContext;
  onClose: () => void;
}

const TAB_CONTENT = cn('min-h-0 flex-1 px-4 py-3', SCROLL_Y);

export function StepDetail({
  stepId,
  summary,
  detail,
  context,
  onClose,
}: StepDetailProps) {
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
      className="flex h-full min-h-0 flex-col"
    >
      <header className="flex items-center gap-2 border-b px-4 py-2">
        {step ? <KindBadge kind={step.kind} className="shrink-0" /> : null}
        <h2 className="min-w-0 flex-1 truncate text-sm font-medium">
          {step?.name ?? `Step ${stepId}`}
        </h2>
        <span className="text-xs text-muted-foreground tabular-nums">
          #{stepId}
        </span>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label="Close details"
          title="Close (Esc)"
          onClick={onClose}
        >
          <X aria-hidden />
        </Button>
      </header>
      {step ? (
        <Tabs defaultValue="overview" className="min-h-0 flex-1 gap-0">
          <TabsList variant="line" className="h-9 shrink-0 px-2">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="request">Request</TabsTrigger>
            <TabsTrigger value="response">Response</TabsTrigger>
            <TabsTrigger value="timing">Timing</TabsTrigger>
            <TabsTrigger value="chain">Chain</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className={TAB_CONTENT}>
            <OverviewTab step={step} context={context} />
          </TabsContent>
          <TabsContent value="request" className={TAB_CONTENT}>
            <BodyTab part="request" detail={detail} />
          </TabsContent>
          <TabsContent value="response" className={TAB_CONTENT}>
            <BodyTab part="response" detail={detail} />
          </TabsContent>
          <TabsContent value="timing" className={TAB_CONTENT}>
            <TimingTab step={step} context={context} />
          </TabsContent>
          <TabsContent value="chain" className={TAB_CONTENT}>
            <ChainTab step={step} context={context} />
          </TabsContent>
        </Tabs>
      ) : (
        <DetailFallback detail={detail} />
      )}
    </section>
  );
}

function DetailFallback({ detail }: { detail: Detail }) {
  if (detail.phase === 'error' || detail.phase === 'unavailable') {
    return (
      <Notice title="This step could not be loaded" tone="error">
        {detail.message}
      </Notice>
    );
  }
  return <BodySkeleton />;
}
