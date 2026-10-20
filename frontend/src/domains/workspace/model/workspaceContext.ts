import { createContext, useContext } from 'react';

import type { UserActionRequest } from '../api/auditSchema';
import type { WorkspaceClient } from '../api/contract';
import type {
  GraphView,
  SourceDecisionRequest,
  TraceEvent,
  WorkspaceState,
} from '../api/schema';
import type { EventStreamStatus } from './useWorkspaceEvents';

export type WorkspaceLoad =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; state: WorkspaceState; graph: GraphView }
  | { status: 'error'; message: string };

export interface WorkspaceContextValue {
  client: WorkspaceClient;
  /** Open workspace, or null when none is open. */
  workspaceId: string | null;
  load: WorkspaceLoad;
  events: readonly TraceEvent[];
  eventStatus: EventStreamStatus;
  /** Open another workspace (the app router decides how), or none. */
  openWorkspace: (id: string | null) => void;
  /** Fetch the state and graph again. The current data stays visible. */
  reload: () => void;
  /**
   * Start the run, or continue it from AWAITING_REVIEW, then reconnect the
   * event stream and reload. Rejects with the API error.
   */
  startRun: () => Promise<void>;
  /**
   * Include or exclude a source by hand, then reload. The server records the
   * decision in the trajectory. Rejects with the API error.
   */
  decideSource: (
    sourceId: string,
    body: SourceDecisionRequest,
  ) => Promise<void>;
  /**
   * Re-synthesize with the pending source decisions, then reconnect the event
   * stream and reload. Rejects with the API error.
   */
  resynthesize: () => Promise<void>;
  /** Record a UI action in the trajectory (best effort, never throws). */
  recordAction: (action: UserActionRequest) => void;
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
