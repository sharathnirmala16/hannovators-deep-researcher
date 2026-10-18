import { Button } from '@/shared/ui/button';

import type { LoadPhase } from '../model/trajectoryState';
import { Notice } from './Notice';

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
      <Notice title="The trajectory is not available yet">
        This server does not serve trajectory steps yet. The audit view fills in
        as soon as the trajectory API is deployed.
        <span className="mt-1 block font-mono text-xs">{load.message}</span>
      </Notice>
    );
  }
  if (load.phase === 'error') {
    return (
      <Notice
        title="The trajectory could not be loaded"
        tone="error"
        action={
          <Button size="xs" variant="outline" onClick={onRetry}>
            Try again
          </Button>
        }
      >
        {load.message}
      </Notice>
    );
  }
  return (
    <div aria-busy className="flex flex-col" aria-label="Loading steps">
      {Array.from({ length: 12 }, (_, index) => (
        <div key={index} className="flex h-7 items-center gap-4 px-3">
          <span className="h-2.5 w-8 rounded-sm bg-muted motion-safe:animate-pulse" />
          <span className="h-2.5 w-20 rounded-sm bg-muted motion-safe:animate-pulse" />
          <span
            className="h-2.5 rounded-sm bg-muted motion-safe:animate-pulse"
            style={{ width: `${20 + ((index * 37) % 40)}%` }}
          />
        </div>
      ))}
    </div>
  );
}
