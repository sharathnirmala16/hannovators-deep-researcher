import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import {
  apiErrorStatus,
  isUnavailable,
  useWorkspace,
  type DeepResearchRecord,
} from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';

export type DeepResearchLoad =
  | { status: 'loading' }
  | { status: 'ready'; record: DeepResearchRecord | null }
  | { status: 'unavailable' }
  | { status: 'error'; message: string };

const POLL_MS = 5000;
const PROGRESS_PREFIX = 'Tavily deep research';

const isRunning = (load: DeepResearchLoad) =>
  load.status === 'ready' &&
  (load.record?.status === 'pending' || load.record?.status === 'running');

function toLoad(error: unknown): DeepResearchLoad {
  return isUnavailable(error)
    ? { status: 'unavailable' }
    : { status: 'error', message: errorMessage(error) };
}

/**
 * The Tavily deep research record: fetched on open, polled while it runs,
 * and refetched when a "Tavily deep research" progress event arrives.
 */
export function useDeepResearch() {
  const { client, workspaceId, events } = useWorkspace();
  const [load, setLoad] = useState<DeepResearchLoad>({ status: 'loading' });
  const [token, setToken] = useState(0);
  const [starting, setStarting] = useState(false);
  const refetch = useCallback(() => setToken((value) => value + 1), []);

  const progress = events.filter(
    (event) =>
      event.kind === 'PROGRESS' && event.message.startsWith(PROGRESS_PREFIX),
  ).length;

  useEffect(() => {
    if (!workspaceId) return undefined;
    const controller = new AbortController();
    client.getDeepResearch(workspaceId, controller.signal).then(
      (record) => setLoad({ status: 'ready', record }),
      (error: unknown) => {
        if (!controller.signal.aborted) setLoad(toLoad(error));
      },
    );
    return () => controller.abort();
  }, [client, workspaceId, token, progress]);

  const running = isRunning(load);
  useEffect(() => {
    if (!running) return undefined;
    const timer = setInterval(refetch, POLL_MS);
    return () => clearInterval(timer);
  }, [running, refetch]);

  const start = async () => {
    if (!workspaceId) return;
    setStarting(true);
    try {
      const record = await client.startDeepResearch(workspaceId);
      setLoad({ status: 'ready', record });
    } catch (error) {
      if (apiErrorStatus(error) === 409) refetch();
      else if (isUnavailable(error)) setLoad({ status: 'unavailable' });
      else toast.error(`Deep research did not start: ${errorMessage(error)}`);
    }
    setStarting(false);
  };

  return { load, running, starting, start, refetch };
}
