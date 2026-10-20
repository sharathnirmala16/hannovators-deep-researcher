import { useEffect, useState, type RefObject } from 'react';

/** Pages within this margin of the viewport render; the rest stay empty. */
const NEAR_MARGIN = '150% 0px';

function pageOf(element: Element): number {
  return Number((element as HTMLElement).dataset.page);
}

/**
 * The page numbers near the scroll viewport. Pages are the `[data-page]`
 * children of `rootRef`; observing starts once `enabled` (the pages exist).
 */
export function useNearPages(
  rootRef: RefObject<HTMLElement | null>,
  enabled: boolean,
): ReadonlySet<number> {
  const [near, setNear] = useState<ReadonlySet<number>>(() => new Set());

  useEffect(() => {
    const root = rootRef.current;
    if (!root || !enabled) return undefined;
    const observer = new IntersectionObserver(
      (entries) =>
        setNear((previous) => {
          const next = new Set(previous);
          for (const entry of entries) {
            if (entry.isIntersecting) next.add(pageOf(entry.target));
            else next.delete(pageOf(entry.target));
          }
          return next;
        }),
      { root, rootMargin: NEAR_MARGIN },
    );
    for (const page of root.querySelectorAll('[data-page]')) {
      observer.observe(page);
    }
    return () => observer.disconnect();
  }, [rootRef, enabled]);

  return near;
}
