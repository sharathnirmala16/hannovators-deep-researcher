import { createContext, useContext } from 'react';

import { WorkspaceApiError, type WorkspaceClient } from '../api/contract';
import { workspaceClient } from '../api/workspaceClient';

/** The active data source (HTTP or fixtures). Tests may provide another. */
export const WorkspaceClientContext =
  createContext<WorkspaceClient>(workspaceClient);

/** The client outside an open workspace (for example the workspaces page). */
export function useWorkspaceClient(): WorkspaceClient {
  return useContext(WorkspaceClientContext);
}

/** HTTP status of a failed API call, or null for other errors. */
export function apiErrorStatus(error: unknown): number | null {
  return error instanceof WorkspaceApiError ? error.status : null;
}

/**
 * True when the server has no implementation yet (501) or the fixture client
 * cannot serve the call. The UI shows "not available" instead of an error.
 */
export function isUnavailable(error: unknown): boolean {
  return apiErrorStatus(error) === 501;
}
