import { useMemo } from 'react';

import { useWorkspace } from '@/domains/workspace';
import { TooltipProvider } from '@/shared/ui/tooltip';

import { trajectorySource } from '../api/trajectorySource';
import { Notice } from './Notice';
import { TrajectoryWorkspace } from './TrajectoryWorkspace';

interface TrajectoryViewProps {
  /**
   * Called after a linked source is selected (the selection store already has
   * it), so the shell can switch to the Research tab.
   */
  onOpenSource?: (sourceId: string) => void;
}

/**
 * Network-tab style audit of every agent and user action of the open
 * workspace: filters, stage swimlanes, a windowed step table with a waterfall,
 * and a detail panel with the request and response bodies.
 */
export function TrajectoryView({ onOpenSource }: TrajectoryViewProps) {
  const { client, workspaceId } = useWorkspace();
  const source = useMemo(
    () => (workspaceId ? trajectorySource(client, workspaceId) : null),
    [client, workspaceId],
  );
  if (!source) {
    return (
      <Notice title="No workspace is open">
        Open or create a workspace. Its trajectory lists every search, fetch,
        model call, decision, verdict, and user action of the run.
      </Notice>
    );
  }
  return (
    <TooltipProvider delayDuration={300}>
      <TrajectoryWorkspace
        key={source.workspaceId}
        source={source}
        onOpenSource={onOpenSource}
      />
    </TooltipProvider>
  );
}
