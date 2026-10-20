import { useMemo } from 'react';

import { useWorkspace } from '@/domains/workspace';
import { EmptyState } from '@/shared/ui/states';
import { TooltipProvider } from '@/shared/ui/tooltip';

import { trajectorySource } from '../api/trajectorySource';
import { TrajectoryWorkspace } from './TrajectoryWorkspace';

interface TrajectoryViewProps {
  /**
   * Called after a linked source is selected (the selection store already has
   * it), so the shell can switch to the Research tab.
   */
  onOpenSource?: (sourceId: string) => void;
  /** A step to open, from a `?step=<id>` deep link. */
  step?: number | null;
}

/**
 * Network-tab style audit of every agent and user action of the open
 * workspace: filters, stage swimlanes, a windowed step table with a waterfall,
 * and a detail panel with the request and response bodies.
 */
export function TrajectoryView({
  onOpenSource,
  step = null,
}: TrajectoryViewProps) {
  const { client, workspaceId } = useWorkspace();
  const source = useMemo(
    () => (workspaceId ? trajectorySource(client, workspaceId) : null),
    [client, workspaceId],
  );
  if (!source) {
    return (
      <div className="p-4">
        <EmptyState title="No workspace is open">
          Open or create a workspace. Its trajectory lists every search, fetch,
          model call, decision, verdict, and user action of the run.
        </EmptyState>
      </div>
    );
  }
  return (
    <TooltipProvider delayDuration={300}>
      <TrajectoryWorkspace
        key={source.workspaceId}
        source={source}
        onOpenSource={onOpenSource}
        step={step}
      />
    </TooltipProvider>
  );
}
