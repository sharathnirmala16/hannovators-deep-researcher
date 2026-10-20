import { useCallback, useEffect, useState } from 'react';

import { useWorkspace, type SourceDetail } from '@/domains/workspace';

export type DetailLoad =
  | { status: 'loading' }
  | { status: 'ready'; detail: SourceDetail }
  | { status: 'error'; error: unknown };

interface Loaded {
  key: string;
  load: DetailLoad;
}

/** Fetches the audit record of one source; `retry` fetches it again. */
export function useSourceDetail(sourceId: string | null): {
  load: DetailLoad;
  retry: () => void;
} {
  const { client, workspaceId } = useWorkspace();
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const key = `${workspaceId ?? ''}|${sourceId ?? ''}|${attempt}`;

  useEffect(() => {
    if (!workspaceId || !sourceId) return undefined;
    const controller = new AbortController();
    client.getSource(workspaceId, sourceId, controller.signal).then(
      (detail) => setLoaded({ key, load: { status: 'ready', detail } }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setLoaded({ key, load: { status: 'error', error } });
        }
      },
    );
    return () => controller.abort();
  }, [client, workspaceId, sourceId, key]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  // A result for another source (or an older attempt) counts as loading.
  const load: DetailLoad =
    loaded && loaded.key === key ? loaded.load : { status: 'loading' };
  return { load, retry };
}
