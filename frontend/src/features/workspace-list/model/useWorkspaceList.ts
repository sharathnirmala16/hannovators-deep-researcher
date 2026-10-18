import { useCallback, useEffect, useState } from 'react';

import {
  isUnavailable,
  useWorkspaceClient,
  type WorkspaceSummary,
} from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';

export type WorkspaceListLoad =
  | { status: 'loading' }
  | { status: 'ready'; items: WorkspaceSummary[] }
  | { status: 'unavailable' }
  | { status: 'error'; message: string };

/** Recent workspaces, newest first, with a reload. */
export function useWorkspaceList() {
  const client = useWorkspaceClient();
  const [token, setToken] = useState(0);
  const [load, setLoad] = useState<WorkspaceListLoad>({ status: 'loading' });

  useEffect(() => {
    const controller = new AbortController();
    client.listWorkspaces(controller.signal).then(
      (items) => setLoad({ status: 'ready', items }),
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setLoad(
          isUnavailable(error)
            ? { status: 'unavailable' }
            : { status: 'error', message: errorMessage(error) },
        );
      },
    );
    return () => controller.abort();
  }, [client, token]);

  const reload = useCallback(() => setToken((value) => value + 1), []);
  return { load, reload };
}
