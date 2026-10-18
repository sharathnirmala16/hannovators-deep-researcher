import { useState } from 'react';

/**
 * Views seen so far. A view mounts on its first visit and then stays mounted
 * (hidden), so its state, streams, and scroll position survive switches.
 */
export function useVisited<T extends string>(current: T): ReadonlySet<T> {
  const [visited, setVisited] = useState<ReadonlySet<T>>(
    () => new Set([current]),
  );
  if (!visited.has(current)) {
    const next = new Set([...visited, current]);
    setVisited(next);
    return next;
  }
  return visited;
}
