import { useEffect, useState, type RefObject } from 'react';

const RESIZE_DEBOUNCE_MS = 150;

/**
 * The element's content width, measured at once and then debounced while it
 * resizes. A hidden element (width 0) keeps the last known width.
 */
export function useContainerWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    let first = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.floor(entry?.contentRect.width ?? 0);
      if (next <= 0) return;
      clearTimeout(timer);
      timer = setTimeout(() => setWidth(next), first ? 0 : RESIZE_DEBOUNCE_MS);
      first = false;
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, [ref]);

  return width;
}
