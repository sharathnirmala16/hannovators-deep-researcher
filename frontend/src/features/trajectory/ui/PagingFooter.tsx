import { Button } from '@/shared/ui/button';

export interface PagingState {
  hasMore: boolean;
  loadingMore: boolean;
  error: string | null;
  onLoadMore: () => void;
}

/**
 * Below the last row: paging progress, a retry, or the end of the record.
 * Outside the table, so it never adds phantom columns to the fixed layout.
 */
export function PagingFooter({ paging }: { paging: PagingState }) {
  const { hasMore, loadingMore, error, onLoadMore } = paging;
  let content = (
    <span className="text-muted-foreground">End of the trajectory</span>
  );
  if (loadingMore) {
    content = <span className="text-muted-foreground">Loading more steps</span>;
  } else if (error) {
    content = (
      <span className="flex items-center gap-2 text-tone-negative">
        Could not load more steps: {error}
        <Button size="xs" variant="outline" onClick={onLoadMore}>
          Try again
        </Button>
      </span>
    );
  } else if (hasMore) {
    content = (
      <Button size="xs" variant="ghost" onClick={onLoadMore}>
        Load more steps
      </Button>
    );
  }
  return <div className="flex h-10 items-center px-4 text-xs">{content}</div>;
}
