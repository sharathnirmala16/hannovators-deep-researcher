import type { WorkspaceClient } from './contract';
import { fixtureClient } from './fixtureClient';
import { httpClient } from './httpClient';

/** `VITE_USE_FIXTURES=1` serves the recorded fixtures instead of the API. */
export const workspaceClient: WorkspaceClient =
  import.meta.env.VITE_USE_FIXTURES === '1' ? fixtureClient : httpClient;
