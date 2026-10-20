import { useCallback, useEffect, type RefObject } from 'react';

/** Load the next page when the user scrolls within this many rows of the end. */
const END_THRESHOLD_ROWS = 8;

interface Paging {
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
}

/**
 * Infinite paging for a scroll container: loads while the rows do not fill
 * the viewport, and returns a scroll handler that loads near the end.
 */
export function useEndPaging(
  ref: RefObject<HTMLElement | null>,
  rowCount: number,
  paging: Paging,
  rowHeight: number,
): () => void {
  const { hasMore, loadingMore, onLoadMore } = paging;

  useEffect(() => {
    const element = ref.current;
    if (!element || !hasMore || loadingMore) return;
    if (element.scrollHeight <= element.clientHeight + rowHeight) onLoadMore();
  }, [ref, rowCount, hasMore, loadingMore, onLoadMore, rowHeight]);

  return useCallback(() => {
    const element = ref.current;
    if (!element || !hasMore || loadingMore) return;
    const left =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    if (left < rowHeight * END_THRESHOLD_ROWS) onLoadMore();
  }, [ref, hasMore, loadingMore, onLoadMore, rowHeight]);
}
