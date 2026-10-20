import type { WorkspaceState } from '@/domains/workspace';
import { EmptyState } from '@/shared/ui/states';

import { citationIndex } from './citations';
import { OutcomeProfile } from './OutcomeProfile';

/** MEDICAL: GRADE evidence profile, one block per synthesized outcome. */
export function EvidenceProfile({ state }: { state: WorkspaceState }) {
  const summaries = state.synthesis?.pairwise_summaries ?? [];
  if (summaries.length === 0) {
    return (
      <EmptyState className="mx-4" title="No evidence profile yet">
        The GRADE profile is built in the synthesis stage. Run or continue the
        workspace from the plan pane; included studies then appear here, one
        table per outcome.
      </EmptyState>
    );
  }
  const citations = citationIndex(state);
  return (
    <div className="flex flex-col gap-8">
      {summaries.map((summary) => (
        <OutcomeProfile
          key={`${summary.intervention}|${summary.comparison}|${summary.outcome}`}
          summary={summary}
          state={state}
          citations={citations}
        />
      ))}
    </div>
  );
}
