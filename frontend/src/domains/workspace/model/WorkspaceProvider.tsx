import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import type { WorkspaceClient } from '../api/contract';
import { workspaceClient } from '../api/workspaceClient';
import { useWorkspaceEvents } from './useWorkspaceEvents';
import {
  WorkspaceContext,
  type WorkspaceContextValue,
  type WorkspaceLoad,
} from './workspaceContext';

const WORKSPACE_PARAM = 'workspace';

interface LoadResult {
  workspaceId: string;
  load: WorkspaceLoad;
}

/** `undefined` means "use the client's default workspace". */
function readUrlWorkspaceId(): string | undefined {
  const id = new URLSearchParams(window.location.search).get(WORKSPACE_PARAM);
  return id || undefined;
}

function writeUrlWorkspaceId(id: string | null): void {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set(WORKSPACE_PARAM, id);
  else url.searchParams.delete(WORKSPACE_PARAM);
  window.history.replaceState(window.history.state, '', url);
}

async function loadWorkspace(
  client: WorkspaceClient,
  id: string,
  signal: AbortSignal,
): Promise<WorkspaceLoad> {
  try {
    const [state, graph] = await Promise.all([
      client.getWorkspace(id, signal),
      client.getGraph(id, signal),
    ]);
    return { status: 'ready', state, graph };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { status: 'error', message };
  }
}

interface WorkspaceProviderProps {
  children: ReactNode;
  client?: WorkspaceClient;
}

/** Loads one workspace and its trace events for the whole app. */
export function WorkspaceProvider({
  children,
  client = workspaceClient,
}: WorkspaceProviderProps) {
  const [workspaceId, setWorkspaceId] = useState<string | null | undefined>(
    readUrlWorkspaceId,
  );
  const [reloadToken, setReloadToken] = useState(0);
  const [result, setResult] = useState<LoadResult | null>(null);
  const openId = workspaceId ?? null;
  const { events, status: eventStatus } = useWorkspaceEvents(client, openId);

  useEffect(() => {
    if (workspaceId !== undefined) return undefined;
    let active = true;
    const resolve = (id: string | null) => {
      if (active) setWorkspaceId(id);
    };
    client.defaultWorkspaceId().then(resolve, () => resolve(null));
    return () => {
      active = false;
    };
  }, [client, workspaceId]);

  useEffect(() => {
    if (!workspaceId) return undefined;
    const controller = new AbortController();
    void loadWorkspace(client, workspaceId, controller.signal).then((load) => {
      if (!controller.signal.aborted) setResult({ workspaceId, load });
    });
    return () => controller.abort();
  }, [client, workspaceId, reloadToken]);

  const openWorkspace = useCallback((id: string | null) => {
    writeUrlWorkspaceId(id);
    setWorkspaceId(id);
  }, []);
  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  const value = useMemo<WorkspaceContextValue>(() => {
    let load: WorkspaceLoad = { status: 'loading' };
    if (workspaceId === null) load = { status: 'idle' };
    else if (result && result.workspaceId === workspaceId) load = result.load;
    return {
      client,
      workspaceId: openId,
      load,
      events,
      eventStatus,
      openWorkspace,
      reload,
    };
  }, [
    client,
    workspaceId,
    openId,
    result,
    events,
    eventStatus,
    openWorkspace,
    reload,
  ]);

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}
