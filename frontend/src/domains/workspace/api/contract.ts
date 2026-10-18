import type {
  CreateWorkspaceRequest,
  GraphView,
  TraceEvent,
  WorkspaceState,
  WorkspaceView,
} from './schema';

export interface WorkspaceEventHandlers {
  onEvent: (event: TraceEvent) => void;
  /** The server sent `event: end` after the final STATUS event. */
  onEnd: () => void;
  onError: (error: Error) => void;
}

/**
 * Data source for one research workspace. The HTTP client and the fixture
 * client both implement it, so features never know which one is active.
 */
export interface WorkspaceClient {
  readonly source: 'http' | 'fixtures';
  /** Workspace to open when the URL names none, or null for a new run. */
  defaultWorkspaceId: () => Promise<string | null>;
  getWorkspace: (id: string, signal?: AbortSignal) => Promise<WorkspaceState>;
  getGraph: (id: string, signal?: AbortSignal) => Promise<GraphView>;
  createWorkspace: (body: CreateWorkspaceRequest) => Promise<WorkspaceView>;
  /** Start the run, or continue it from AWAITING_REVIEW. */
  runWorkspace: (id: string) => Promise<void>;
  /** Subscribe to trace events. Returns a function that closes the stream. */
  subscribeEvents: (id: string, handlers: WorkspaceEventHandlers) => () => void;
}

/** A failed API call, normalized from the `ApiError` body when present. */
export class WorkspaceApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'WorkspaceApiError';
    this.status = status;
    this.code = code;
  }
}
