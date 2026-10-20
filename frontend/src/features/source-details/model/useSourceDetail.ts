import { useCallback, useEffect, useState } from 'react';

import { useWorkspace, type SourceDetail } from '@/domains/workspace';

export type DetailLoad =
  | { status: 'loading' }
  | { status: 'ready'; detail: SourceDetail }
  | { status: 'error'; error: unknown };

interface Loaded {
  key: string;
  /** The key without the version: same workspace, source, and attempt. */
  identity: string;
  load: DetailLoad;
}

/**
 * Fetches the audit record of one source; `retry` fetches it again, and so
 * does a new `version` (the source's status or decision changed).
 */
export function useSourceDetail(
  sourceId: string | null,
  version = '',
): {
  load: DetailLoad;
  retry: () => void;
} {
  const { client, workspaceId } = useWorkspace();
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const identity = `${workspaceId ?? ''}|${sourceId ?? ''}|${attempt}`;
  const key = `${identity}|${version}`;

  useEffect(() => {
    if (!workspaceId || !sourceId) return undefined;
    const controller = new AbortController();
    client.getSource(workspaceId, sourceId, controller.signal).then(
      (detail) =>
        setLoaded({ key, identity, load: { status: 'ready', detail } }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setLoaded({ key, identity, load: { status: 'error', error } });
        }
      },
    );
    return () => controller.abort();
  }, [client, workspaceId, sourceId, key, identity]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  // A result for another source (or an older attempt) counts as loading; an
  // older version of the same source stays on screen while it refreshes.
  const current = loaded?.key === key || loaded?.identity === identity;
  const load: DetailLoad =
    loaded && current ? loaded.load : { status: 'loading' };
  return { load, retry };
}
