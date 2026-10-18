import { Loader2Icon, SparklesIcon } from 'lucide-react';

import type { DeepResearchRecord } from '@/domains/workspace';
import { formatDuration, relativeTime } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import { SectionHeader } from '@/shared/ui/section-header';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/ui/states';
import { Tag, type Tone } from '@/shared/ui/tag';

import { useDeepResearch } from '../model/useDeepResearch';
import { DeepResearchReport } from './DeepResearchReport';

const STATUS: Record<
  DeepResearchRecord['status'],
  { label: string; tone: Tone }
> = {
  pending: { label: 'Queued', tone: 'info' },
  running: { label: 'Researching', tone: 'info' },
  completed: { label: 'Report ready', tone: 'positive' },
  failed: { label: 'Failed', tone: 'negative' },
};

function elapsed(record: DeepResearchRecord): string {
  if (!record.started_at || !record.finished_at) return '';
  return formatDuration(
    new Date(record.finished_at).getTime() -
      new Date(record.started_at).getTime(),
  );
}

function Body({ record }: { record: DeepResearchRecord | null }) {
  if (!record) {
    return (
      <EmptyState title="No deep research yet">
        Tavily writes an independent cited report on the same question. Use it
        to cross-check what the pipeline found.
      </EmptyState>
    );
  }
  switch (record.status) {
    case 'pending':
    case 'running':
      return (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">
            Started{' '}
            {record.started_at ? relativeTime(record.started_at) : 'just now'}.
            This takes a few minutes.
          </p>
          <SkeletonBlock lines={4} label="Deep research is running" />
        </div>
      );
    case 'failed':
      return (
        <ErrorState
          title="Deep research failed"
          message={record.error ?? 'The provider gave no reason.'}
        />
      );
    case 'completed':
      return <DeepResearchReport record={record} />;
  }
}

/** Tavily deep research: trigger, status, and the cited report. */
export function DeepResearch() {
  const { load, running, starting, start, refetch } = useDeepResearch();
  const record = load.status === 'ready' ? load.record : null;
  const status = record ? STATUS[record.status] : null;
  const canStart = load.status === 'ready' && !running;

  return (
    <section
      aria-labelledby="deep-research-title"
      className="flex flex-col gap-2"
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
              {record ? <span>{elapsed(record)}</span> : null}
            </>
          ) : null
        }
        actions={
          canStart ? (
            <Button
              size="xs"
              variant={record ? 'ghost' : 'outline'}
              onClick={() => void start()}
              disabled={starting}
            >
              {starting ? (
                <Loader2Icon className="animate-spin" />
              ) : (
                <SparklesIcon />
              )}
              {record ? 'Run again' : 'Run deep research'}
            </Button>
          ) : null
        }
      />
      {load.status === 'loading' ? <SkeletonBlock lines={2} /> : null}
      {load.status === 'unavailable' ? (
        <EmptyState title="Deep research is not available on this server yet" />
      ) : null}
      {load.status === 'error' ? (
        <ErrorState
          title="Could not load the deep research"
          message={load.message}
          onRetry={refetch}
        />
      ) : null}
      {load.status === 'ready' ? <Body record={record} /> : null}
    </section>
  );
}
