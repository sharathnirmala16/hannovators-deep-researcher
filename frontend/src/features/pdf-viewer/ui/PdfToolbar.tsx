import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ExternalLinkIcon,
  MoveHorizontalIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from 'lucide-react';
import { useState, type KeyboardEvent } from 'react';

import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';

interface PdfToolbarProps {
  page: number;
  pageCount: number;
  onPage: (page: number) => void;
  scale: number;
  fit: boolean;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  originalUrl: string;
}

function PageInput({
  page,
  pageCount,
  onPage,
}: Pick<PdfToolbarProps, 'page' | 'pageCount' | 'onPage'>) {
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    const value = Number(draft);
    if (draft !== null && Number.isInteger(value)) {
      onPage(Math.min(Math.max(value, 1), pageCount));
    }
    setDraft(null);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') commit();
    if (event.key === 'Escape') setDraft(null);
  };
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums">
      <span className="sr-only">Page</span>
      <Input
        inputMode="numeric"
        aria-label={`Page number, 1 to ${pageCount}`}
        value={draft ?? String(page)}
        onFocus={(event) => {
          setDraft(String(page));
          event.target.select();
        }}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={onKeyDown}
        className="h-7 w-12 px-1.5 text-center text-xs tabular-nums"
      />
      <span aria-hidden>/ {pageCount}</span>
    </label>
  );
}

/** Page navigation, zoom, and a link to the original file. */
export function PdfToolbar({
  page,
  pageCount,
  onPage,
  scale,
  fit,
  onZoomIn,
  onZoomOut,
  onFit,
  originalUrl,
}: PdfToolbarProps) {
  return (
    <div
      role="toolbar"
      aria-label="Document"
      className="flex items-center gap-1 border-b border-border bg-background px-2 py-1.5"
    >
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Previous page"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
      >
        <ChevronLeftIcon aria-hidden />
      </Button>
      <PageInput page={page} pageCount={pageCount} onPage={onPage} />
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Next page"
        disabled={page >= pageCount}
        onClick={() => onPage(page + 1)}
      >
        <ChevronRightIcon aria-hidden />
      </Button>
      <div className="mx-1 h-4 w-px bg-border" aria-hidden />
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Zoom out"
        onClick={onZoomOut}
      >
        <ZoomOutIcon aria-hidden />
      </Button>
      <span className="w-10 text-center text-xs text-muted-foreground tabular-nums">
        {Math.round(scale * 100)}%
      </span>
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Zoom in"
        onClick={onZoomIn}
      >
        <ZoomInIcon aria-hidden />
      </Button>
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Fit width"
        aria-pressed={fit}
        onClick={onFit}
      >
        <MoveHorizontalIcon aria-hidden />
      </Button>
      <a
        href={originalUrl}
        target="_blank"
        rel="noreferrer"
        className="ml-auto inline-flex items-center gap-1 rounded-sm px-1.5 py-1 text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        Open original
        <ExternalLinkIcon aria-hidden className="size-3" />
      </a>
    </div>
  );
}
