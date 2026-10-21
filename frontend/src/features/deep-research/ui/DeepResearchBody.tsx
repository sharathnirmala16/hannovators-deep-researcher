import type { ReactNode } from 'react';

import type { DeepResearchRecord } from '@/domains/workspace';
import { relativeTime } from '@/shared/lib/format';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/ui/states';

import { DeepResearchSummary } from './DeepResearchSummary';

interface DeepResearchBodyProps {
  record: DeepResearchRecord | null;
  /** The start button, offered when nothing has run yet. */
  trigger: ReactNode;
}

/** Idle, running, failed, or the finished report's summary. */
export function DeepResearchBody({ record, trigger }: DeepResearchBodyProps) {
  if (!record) {
    return (
      <EmptyState title="No deep research yet" action={trigger}>
        Tavily writes an independent cited report on the same question. Use it
        to cross-check what the pipeline found.
      </EmptyState>
    );
  }
  switch (record.status) {
    case 'pending':
    case 'running':
      return (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-muted-foreground">
            Started{' '}
            {record.started_at ? relativeTime(record.started_at) : 'just now'}.
            This takes a few minutes; the report is added to the sources when it
            is ready.
          </p>
          <SkeletonBlock lines={4} label="Deep research is running" />
        </div>
      );
    case 'failed':
      return (
        <ErrorState
          title="Deep research failed"
          message={record.error ?? 'The provider gave no reason.'}
        >
          Run it again, or continue with the pipeline results.
        </ErrorState>
      );
    case 'completed':
      return <DeepResearchSummary record={record} />;
  }
}
