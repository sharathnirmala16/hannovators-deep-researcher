import { createContext, useContext } from 'react';

import type { WorkspaceClient } from '../api/contract';
import type { GraphView, TraceEvent, WorkspaceState } from '../api/schema';
import type { EventStreamStatus } from './useWorkspaceEvents';

export type WorkspaceLoad =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; state: WorkspaceState; graph: GraphView }
  | { status: 'error'; message: string };

export interface WorkspaceContextValue {
  client: WorkspaceClient;
  /** Open workspace, or null when none is open (or the default is pending). */
  workspaceId: string | null;
  load: WorkspaceLoad;
  events: readonly TraceEvent[];
  eventStatus: EventStreamStatus;
  /** Open another workspace (for example after a new run), or none. */
  openWorkspace: (id: string | null) => void;
  /** Fetch the state and graph again. The current data stays visible. */
  reload: () => void;
}

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(
  null,
);

export function useWorkspace(): WorkspaceContextValue {
  const value = useContext(WorkspaceContext);
  if (!value) {
    throw new Error('useWorkspace must be used inside a WorkspaceProvider.');
  }
  return value;
}
