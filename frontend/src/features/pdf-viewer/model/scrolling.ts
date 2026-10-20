import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from 'react';

import { toCssBox, type PageGeometry, type PageRect } from './geometry';

const SCROLL_MARGIN = 8;

function scrollBehavior(): ScrollBehavior {
  const reduce =
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  return reduce ? 'auto' : 'smooth';
}

function pageElement(root: HTMLElement, page: number): HTMLElement | null {
  return root.querySelector<HTMLElement>(`[data-page="${page}"]`);
}

/** Scrolls the page's top edge into view. */
export function scrollToPage(root: HTMLElement, page: number): void {
  const element = pageElement(root, page);
  if (!element) return;
  root.scrollTo({
    top: Math.max(0, element.offsetTop - SCROLL_MARGIN),
    behavior: scrollBehavior(),
  });
}

/** Scrolls so the rect sits in the middle of the viewport. */
function scrollToRect(
  root: HTMLElement,
  { page, rect }: PageRect,
  geometry: PageGeometry,
  scale: number,
): void {
  const element = pageElement(root, page);
  if (!element) return;
  const box = toCssBox(rect, geometry, scale);
  const top = element.offsetTop + box.top + box.height / 2;
  // A rect wider than the viewport aligns its start; a narrow one centers.
  const left =
    box.width > root.clientWidth
      ? element.offsetLeft + box.left - SCROLL_MARGIN * 2
      : element.offsetLeft + box.left + box.width / 2 - root.clientWidth / 2;
  root.scrollTo({
    top: Math.max(0, top - root.clientHeight / 2),
    left: Math.max(0, left),
    behavior: scrollBehavior(),
  });
}

/**
 * The page under the upper third of the viewport. Zooming keeps the reading
 * position: the scroll fraction is restored after the pages resize.
 */
export function useScrollTracking(
  rootRef: RefObject<HTMLElement | null>,
  scale: number,
): number {
  const [page, setPage] = useState(1);
  const fraction = useRef(0);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;
    let frame = 0;
    const update = () => {
      frame = 0;
      if (root.scrollHeight <= 0) return;
      fraction.current = root.scrollTop / root.scrollHeight;
      const probe = root.scrollTop + root.clientHeight / 3;
      for (const element of root.querySelectorAll<HTMLElement>('[data-page]')) {
        if (element.offsetTop + element.offsetHeight >= probe) {
          setPage(Number(element.dataset.page));
          return;
        }
      }
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    root.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      root.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(frame);
    };
  }, [rootRef]);

  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root || root.scrollHeight <= 0 || scale <= 0) return;
    root.scrollTop = fraction.current * root.scrollHeight;
  }, [rootRef, scale]);

  return page;
}

interface ScrollTarget {
  rootRef: RefObject<HTMLElement | null>;
  pages: readonly PageGeometry[];
  scale: number;
  /** Changes on every new selection, even of the same item. */
  trigger: unknown;
  page: number | null;
  /** The first rect to center; it may arrive later (quote fallback). */
  anchor: PageRect | undefined;
}

/**
 * Goes to the target page and centers the anchor rect when the selection
 * changes or the anchor arrives. Zooming alone does not jump back.
 */
export function useScrollToTarget(target: ScrollTarget): void {
  const latest = useRef(target);
  useEffect(() => {
    latest.current = target;
  });

  const { trigger, anchor, page } = target;
  const sized = target.scale > 0;
  const anchorKey = anchor
    ? `${anchor.page}:${anchor.rect.join(',')}`
    : `page:${page ?? ''}`;

  useEffect(() => {
    const { rootRef, pages, scale, anchor: rect, page: to } = latest.current;
    const root = rootRef.current;
    if (!root || !sized) return;
    const geometry = rect ? pages[rect.page - 1] : undefined;
    if (rect && geometry) scrollToRect(root, rect, geometry, scale);
    else if (to !== null) scrollToPage(root, to);
  }, [trigger, sized, anchorKey]);
}
