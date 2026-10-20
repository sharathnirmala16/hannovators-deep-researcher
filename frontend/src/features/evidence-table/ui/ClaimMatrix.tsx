import type { WorkspaceState } from '@/domains/workspace';
import { EmptyState } from '@/shared/ui/states';

import { groupByOutcome, indexById } from '../model/evidence';
import { ClaimGroup } from './ClaimGroup';

/** GENERAL: claims per outcome, strongest source first, conflicts visible. */
export function ClaimMatrix({ state }: { state: WorkspaceState }) {
  const groups = groupByOutcome(state.claims);
  if (groups.length === 0) {
    return (
      <EmptyState className="mx-4" title="No claims yet">
        Claims are extracted in the appraisal stage. Run or continue the
        workspace from the plan pane; each claim then appears here with its
        verdict and source.
      </EmptyState>
    );
  }
  const sources = indexById(state.sources);
  return (
    <div className="flex flex-col gap-8">
      {groups.map(([outcome, claims]) => (
        <ClaimGroup
          key={outcome}
          outcome={outcome}
          claims={claims}
          state={state}
          sources={sources}
        />
      ))}
    </div>
  );
}
