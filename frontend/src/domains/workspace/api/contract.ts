import type {
  ChatMessageView,
  DeepResearchRecord,
  SourceDetail,
  TrajectoryPage,
  TrajectoryStep,
  TrajectoryStepSummary,
  UserActionRequest,
  WorkspaceSummary,
} from './auditSchema';
import type {
  CreateWorkspaceRequest,
  Decomposition,
  GraphView,
  SeedReferenceRequest,
  SourceDecisionRequest,
  SourceView,
  TraceEvent,
  TrajectoryKind,
  WorkspaceState,
  WorkspaceView,
} from './schema';

export interface WorkspaceEventHandlers {
  onEvent: (event: TraceEvent) => void;
  /** The server sent `event: end` after the final STATUS event. */
  onEnd: () => void;
  onError: (error: Error) => void;
}

export interface TrajectoryStreamHandlers {
  /** A new step, or a newer version of a step (for example RUNNING -> OK). */
  onStep: (step: TrajectoryStepSummary) => void;
  onError: (error: Error) => void;
}

/** Filters for `GET /api/workspaces/{id}/trajectory` (PLAN.md section 5.3). */
export interface TrajectoryQuery {
  after?: number;
  limit?: number;
  kind?: TrajectoryKind;
  actor?: 'AGENT' | 'USER' | 'SYSTEM';
  stage?: string;
  outcome?: 'KEPT' | 'REMOVED' | 'FLAGGED';
  q?: string;
}

/**
 * Data source for research workspaces. The HTTP client and the fixture client
 * both implement it, so features never know which one is active.
 */
export interface WorkspaceClient {
  readonly source: 'http' | 'fixtures';
  /** Workspace to open when the URL names none, or null for a new run. */
  defaultWorkspaceId: () => Promise<string | null>;
  listWorkspaces: (signal?: AbortSignal) => Promise<WorkspaceSummary[]>;
  getWorkspace: (id: string, signal?: AbortSignal) => Promise<WorkspaceState>;
  getGraph: (id: string, signal?: AbortSignal) => Promise<GraphView>;
  createWorkspace: (body: CreateWorkspaceRequest) => Promise<WorkspaceView>;
  /** Upload seed PDFs (multipart field `files`). */
  uploadSeedFiles: (
    id: string,
    files: readonly File[],
  ) => Promise<SourceView[]>;
  addSeedReference: (
    id: string,
    body: SeedReferenceRequest,
  ) => Promise<SourceView[]>;
  /** Start the run, or continue it from AWAITING_REVIEW. */
  runWorkspace: (id: string) => Promise<void>;
  updateDecomposition: (
    id: string,
    decomposition: Decomposition,
  ) => Promise<WorkspaceState>;
  getSource: (
    id: string,
    sourceId: string,
    signal?: AbortSignal,
  ) => Promise<SourceDetail>;
  /** Include or exclude a source by hand; resolves with the new state. */
  decideSource: (
    id: string,
    sourceId: string,
    body: SourceDecisionRequest,
  ) => Promise<WorkspaceState>;
  /** Re-run the synthesis so pending source decisions take effect. */
  resynthesize: (id: string) => Promise<void>;
  /** Subscribe to trace events. Returns a function that closes the stream. */
  subscribeEvents: (id: string, handlers: WorkspaceEventHandlers) => () => void;
  getTrajectory: (
    id: string,
    query?: TrajectoryQuery,
    signal?: AbortSignal,
  ) => Promise<TrajectoryPage>;
  getTrajectoryStep: (
    id: string,
    stepId: number,
    signal?: AbortSignal,
  ) => Promise<TrajectoryStep>;
  subscribeTrajectory: (
    id: string,
    handlers: TrajectoryStreamHandlers,
  ) => () => void;
  /** Record a UI action in the trajectory. Never throws (best effort). */
  recordAction: (id: string, action: UserActionRequest) => Promise<void>;
  listChat: (id: string, signal?: AbortSignal) => Promise<ChatMessageView[]>;
  /** Ask a question; resolves with the cited assistant answer. */
  ask: (id: string, question: string) => Promise<ChatMessageView>;
  startDeepResearch: (id: string) => Promise<DeepResearchRecord>;
  /** Null when no deep research was started for the workspace. */
  getDeepResearch: (
    id: string,
    signal?: AbortSignal,
  ) => Promise<DeepResearchRecord | null>;
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
