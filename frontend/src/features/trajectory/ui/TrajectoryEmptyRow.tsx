import { Button } from '@/shared/ui/button';

import { hasFilters, type TrajectoryFilters } from '../model/filters';
import { Notice } from './Notice';

interface TrajectoryEmptyRowProps {
  filters: TrajectoryFilters;
  loaded: number;
  onClear: () => void;
}

/** Why the table is empty: nothing recorded yet, or nothing matches. */
export function TrajectoryEmptyRow({
  filters,
  loaded,
  onClear,
}: TrajectoryEmptyRowProps) {
  if (hasFilters(filters)) {
    return (
      <Notice
        title="No steps match these filters"
        action={
          <Button size="xs" variant="outline" onClick={onClear}>
            Clear filters
          </Button>
        }
      >
        {loaded > 0
          ? 'Change or clear the filters to see more of the loaded steps.'
          : 'Change or clear the filters to see more steps.'}
      </Notice>
    );
  }
  return (
    <Notice title="No steps recorded yet">
      Start the run. Every stage, model call, search, fetch, decision, and
      verdict appears here as it happens.
    </Notice>
  );
}
