import { EmptyState, ErrorState } from '@/shared/ui/states';

import type { LoadPhase } from '../model/trajectoryState';
import { SkeletonRows } from './SkeletonRows';

interface TrajectoryBodyStateProps {
  load: LoadPhase;
  onRetry: () => void;
}

/** Loading skeleton, "not available yet" (501), and error states. */
export function TrajectoryBodyState({
  load,
  onRetry,
}: TrajectoryBodyStateProps) {
  if (load.phase === 'unavailable') {
    return (
      <div className="p-4">
        <EmptyState title="The trajectory is not available yet">
          This server does not serve trajectory steps yet. The audit view fills
          in as soon as the trajectory API is deployed.
          <span className="mt-1 block font-mono">{load.message}</span>
        </EmptyState>
      </div>
    );
  }
  if (load.phase === 'error') {
    return (
      <div className="p-4">
        <ErrorState
          title="Could not load the trajectory"
          message={load.message}
          onRetry={onRetry}
        />
      </div>
    );
  }
  return <SkeletonRows />;
}
