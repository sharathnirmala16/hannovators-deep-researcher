import { Loader2Icon, SparklesIcon } from 'lucide-react';

import type { DeepResearchRecord } from '@/domains/workspace';
import { formatDuration } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import { SectionHeader } from '@/shared/ui/section-header';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/ui/states';
import { Tag, type Tone } from '@/shared/ui/tag';

import { useDeepResearch } from '../model/useDeepResearch';
import { DeepResearchBody } from './DeepResearchBody';

const STATUS: Record<
  DeepResearchRecord['status'],
  { label: string; tone: Tone }
> = {
  pending: { label: 'Queued', tone: 'info' },
  running: { label: 'Researching', tone: 'info' },
  completed: { label: 'Report ready', tone: 'positive' },
  failed: { label: 'Failed', tone: 'negative' },
};

function elapsed(record: DeepResearchRecord | null): string {
  if (!record?.started_at || !record.finished_at) return '';
  return formatDuration(
    new Date(record.finished_at).getTime() -
      new Date(record.started_at).getTime(),
  );
}

/** Tavily deep research: trigger, status, and a summary that opens the report source. */
export function DeepResearch() {
  const { load, running, starting, start, refetch } = useDeepResearch();
  const record = load.status === 'ready' ? load.record : null;
  const status = record ? STATUS[record.status] : null;
  const canStart = load.status === 'ready' && !running;
  const icon = starting ? (
    <Loader2Icon className="animate-spin" />
  ) : (
    <SparklesIcon />
  );

  return (
    <section
      aria-labelledby="deep-research-title"
      className="flex min-w-0 flex-col gap-2"
    >
      <SectionHeader
        id="deep-research-title"
        title="Deep research"
        meta={
          status ? (
            <>
              <Tag tone={status.tone} live={running}>
                {status.label}
              </Tag>
              <span>{elapsed(record)}</span>
            </>
          ) : null
        }
        actions={
          canStart && record ? (
            <Button
              size="xs"
              variant="ghost"
              onClick={() => void start()}
              disabled={starting}
            >
              {icon}
              Run again
            </Button>
          ) : null
        }
      />
      {load.status === 'loading' ? (
        <SkeletonBlock lines={3} label="Loading the deep research" />
      ) : null}
      {load.status === 'unavailable' ? (
        <EmptyState title="Deep research is not available on this server">
          This server does not offer deep research yet. The pipeline results are
          not affected.
        </EmptyState>
      ) : null}
      {load.status === 'error' ? (
        <ErrorState
          title="Could not load the deep research"
          message={load.message}
          onRetry={refetch}
        />
      ) : null}
      {load.status === 'ready' ? (
        <DeepResearchBody
          record={record}
          trigger={
            <Button
              size="sm"
              variant="outline"
              onClick={() => void start()}
              disabled={starting}
            >
              {icon}
              Run deep research
            </Button>
          }
        />
      ) : null}
    </section>
  );
}
