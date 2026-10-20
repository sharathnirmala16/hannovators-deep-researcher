import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import type { UserActionRequest } from '../api/auditSchema';
import type { WorkspaceClient } from '../api/contract';
import type { SourceDecisionRequest } from '../api/schema';
import { useWorkspaceClient } from './clientContext';
import { useWorkspaceEvents } from './useWorkspaceEvents';
import {
  WorkspaceContext,
  type WorkspaceContextValue,
  type WorkspaceLoad,
} from './workspaceContext';

/** Reload the state at most this often while events stream in. */
const RELOAD_THROTTLE_MS = 1500;

interface LoadResult {
  workspaceId: string;
  load: WorkspaceLoad;
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

/** Reloads (throttled) whenever new trace events arrive or the stream ends. */
function useLiveReload(signal: string, reload: () => void): void {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (timer.current !== null) return;
    timer.current = setTimeout(() => {
      timer.current = null;
      reload();
    }, RELOAD_THROTTLE_MS);
  }, [signal, reload]);
  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = null;
    },
    [],
  );
}

interface WorkspaceProviderProps {
  /** The workspace chosen by the route, or null for none. */
  workspaceId: string | null;
  children: ReactNode;
  client?: WorkspaceClient;
  /** Called by `openWorkspace`; the app router navigates. */
  onOpenWorkspace?: (id: string | null) => void;
}

/** Loads one workspace, its graph, and its trace events. */
export function WorkspaceProvider({
  workspaceId,
  children,
  client: clientProp,
  onOpenWorkspace,
}: WorkspaceProviderProps) {
  const contextClient = useWorkspaceClient();
  const client = clientProp ?? contextClient;
  const [reloadToken, setReloadToken] = useState(0);
  const [connection, setConnection] = useState(0);
  const [result, setResult] = useState<LoadResult | null>(null);
  const { events, status: eventStatus } = useWorkspaceEvents(
    client,
    workspaceId,
    connection,
  );

  useEffect(() => {
    if (!workspaceId) return undefined;
    const controller = new AbortController();
    void loadWorkspace(client, workspaceId, controller.signal).then((load) => {
      if (controller.signal.aborted) return;
      // A failed background reload keeps the data that is already shown.
      setResult((previous) =>
        load.status === 'error' &&
        previous?.workspaceId === workspaceId &&
        previous.load.status === 'ready'
          ? previous
          : { workspaceId, load },
      );
    });
    return () => controller.abort();
  }, [client, workspaceId, reloadToken]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);
  const lastEventId = events[events.length - 1]?.id ?? 0;
  useLiveReload(`${lastEventId}:${eventStatus}`, reload);

  const openWorkspace = useCallback(
    (id: string | null) => onOpenWorkspace?.(id),
    [onOpenWorkspace],
  );

  const startRun = useCallback(async () => {
    if (!workspaceId) return;
    await client.runWorkspace(workspaceId);
    setConnection((value) => value + 1);
    reload();
  }, [client, workspaceId, reload]);

  const decideSource = useCallback(
    async (sourceId: string, body: SourceDecisionRequest) => {
      if (!workspaceId) return;
      await client.decideSource(workspaceId, sourceId, body);
      reload();
    },
    [client, workspaceId, reload],
  );

  const resynthesize = useCallback(async () => {
    if (!workspaceId) return;
    await client.resynthesize(workspaceId);
    setConnection((value) => value + 1);
    reload();
  }, [client, workspaceId, reload]);

  const recordAction = useCallback(
    (action: UserActionRequest) => {
      if (workspaceId) void client.recordAction(workspaceId, action);
    },
    [client, workspaceId],
  );

  const value = useMemo<WorkspaceContextValue>(() => {
    let load: WorkspaceLoad = { status: 'loading' };
    if (workspaceId === null) load = { status: 'idle' };
    else if (result && result.workspaceId === workspaceId) load = result.load;
    return {
      client,
      workspaceId,
      load,
      events,
      eventStatus,
      openWorkspace,
      reload,
      startRun,
      decideSource,
      resynthesize,
      recordAction,
    };
  }, [
    client,
    workspaceId,
    result,
    events,
    eventStatus,
    openWorkspace,
    reload,
    startRun,
    decideSource,
    resynthesize,
    recordAction,
  ]);

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}
