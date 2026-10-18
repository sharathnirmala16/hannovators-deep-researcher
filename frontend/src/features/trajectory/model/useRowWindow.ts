import { useCallback, useEffect, useState, type RefObject } from 'react';

/** Rows rendered above and below the viewport. */
const OVERSCAN = 12;

export interface RowWindow {
  start: number;
  end: number;
  /** Spacer heights in px above and below the rendered rows. */
  padTop: number;
  padBottom: number;
  onScroll: () => void;
  /** Scrolls the least distance that shows row `index` below the header. */
  reveal: (index: number) => void;
}

interface Viewport {
  top: number;
  height: number;
}

/**
 * Fixed-height row windowing for the trajectory table: only the rows in view
 * (plus overscan) mount, so thousands of steps scroll smoothly.
 */
export function useRowWindow(
  ref: RefObject<HTMLElement | null>,
  count: number,
  rowHeight: number,
  headerHeight: number,
): RowWindow {
  const [viewport, setViewport] = useState<Viewport>({ top: 0, height: 600 });

  const measure = useCallback(() => {
    const element = ref.current;
    if (!element) return;
    setViewport((previous) => {
      const next = { top: element.scrollTop, height: element.clientHeight };
      return previous.top === next.top && previous.height === next.height
        ? previous
        : next;
    });
  }, [ref]);

  useEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref, measure]);

  const reveal = useCallback(
    (index: number) => {
      const element = ref.current;
      if (!element) return;
      const top = index * rowHeight;
      const visible = element.clientHeight - headerHeight;
      if (top < element.scrollTop) element.scrollTop = top;
      else if (top + rowHeight > element.scrollTop + visible) {
        element.scrollTop = top + rowHeight - visible;
      }
    },
    [ref, rowHeight, headerHeight],
  );

  const first = Math.floor(viewport.top / rowHeight);
  const start = Math.max(0, first - OVERSCAN);
  const shown = Math.ceil(viewport.height / rowHeight);
  const end = Math.min(count, first + shown + OVERSCAN);
  return {
    start,
    end,
    padTop: start * rowHeight,
    padBottom: Math.max(0, (count - end) * rowHeight),
    onScroll: measure,
    reveal,
  };
}
