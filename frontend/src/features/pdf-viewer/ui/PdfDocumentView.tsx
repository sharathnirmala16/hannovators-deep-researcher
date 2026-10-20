import { useMemo, useRef, useState } from 'react';

import { ErrorState, Skeleton } from '@/shared/ui/states';

import {
  pageCssSize,
  type PageGeometry,
  type PageRect,
} from '../model/geometry';
import type { PDFDocumentProxy } from '../model/pdfjs';
import {
  scrollToPage,
  useScrollTracking,
  useScrollToTarget,
} from '../model/scrolling';
import type { ViewerTarget } from '../model/targets';
import { useContainerWidth } from '../model/useContainerWidth';
import { useNearPages } from '../model/useNearPages';
import { usePdfDocument } from '../model/usePdfDocument';
import { useQuoteFallback } from '../model/useQuoteFallback';
import { PdfPage } from './PdfPage';
import { PdfToolbar } from './PdfToolbar';

const MIN_SCALE = 0.25;
const MAX_SCALE = 4;
const ZOOM_STEP = 1.25;
/** Horizontal room around a fit-to-width page (padding and scrollbar). */
const PAGE_GUTTER = 32;
const NO_RECTS: readonly PageRect[] = [];

const clampScale = (value: number) =>
  Math.min(Math.max(value, MIN_SCALE), MAX_SCALE);

function byPage(rects: readonly PageRect[]): Map<number, PageRect[]> {
  const map = new Map<number, PageRect[]>();
  for (const item of rects) {
    map.set(item.page, [...(map.get(item.page) ?? []), item]);
  }
  return map;
}

interface DocumentProps {
  url: string;
  target: ViewerTarget;
  /** The evidence selection; a new value re-scrolls to the target. */
  trigger: unknown;
}

interface PagesProps extends DocumentProps {
  pdf: PDFDocumentProxy;
  pages: readonly PageGeometry[];
}

function PdfPages({ pdf, pages, url, target, trigger }: PagesProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const width = useContainerWidth(rootRef);
  const [zoom, setZoom] = useState<number | null>(null);
  const widest = useMemo(
    () => Math.max(1, ...pages.map((page) => pageCssSize(page, 1).width)),
    [pages],
  );
  const fitScale = width > 0 ? clampScale((width - PAGE_GUTTER) / widest) : 0;
  const scale = zoom ?? fitScale;
  const near = useNearPages(rootRef, scale > 0);
  const fallback = useQuoteFallback(
    pdf,
    target.page,
    target.active.length > 0 ? null : target.quote,
  );
  const active = target.active.length > 0 ? target.active : fallback;
  const activeByPage = useMemo(() => byPage(active), [active]);
  const faintByPage = useMemo(() => byPage(target.faint), [target.faint]);
  const current = useScrollTracking(rootRef, scale);
  useScrollToTarget({
    rootRef,
    pages,
    scale,
    trigger,
    page: target.page,
    anchor: active[0],
  });

  const goTo = (page: number) => {
    if (rootRef.current) scrollToPage(rootRef.current, page);
  };
  const zoomBy = (factor: number) => setZoom(clampScale((scale || 1) * factor));

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PdfToolbar
        page={Math.min(current, pages.length)}
        pageCount={pages.length}
        onPage={goTo}
        scale={scale}
        fit={zoom === null}
        onZoomIn={() => zoomBy(ZOOM_STEP)}
        onZoomOut={() => zoomBy(1 / ZOOM_STEP)}
        onFit={() => setZoom(null)}
        originalUrl={url}
      />
      <div
        ref={rootRef}
        className="scroll-xy relative min-h-0 flex-1 bg-muted"
        aria-label="Document pages"
      >
        {scale > 0 ? (
          <div className="flex w-max min-w-full flex-col gap-3 p-3">
            {pages.map((geometry) => (
              <PdfPage
                key={geometry.page}
                pdf={pdf}
                geometry={geometry}
                scale={scale}
                near={near.has(geometry.page)}
                active={activeByPage.get(geometry.page) ?? NO_RECTS}
                faint={faintByPage.get(geometry.page) ?? NO_RECTS}
              />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function LoadingPages() {
  return (
    <div role="status" className="flex flex-1 flex-col gap-3 bg-muted p-3">
      <span className="sr-only">Loading the PDF</span>
      <Skeleton className="aspect-[612/792] w-full bg-background" />
      <Skeleton className="aspect-[612/792] w-full bg-background" />
    </div>
  );
}

/** The source PDF rendered with pdf.js, with highlights drawn on top. */
export function PdfDocumentView(props: DocumentProps) {
  const load = usePdfDocument(props.url);
  if (load.status === 'loading') return <LoadingPages />;
  if (load.status === 'error') {
    return (
      <div className="p-4">
        <ErrorState title="The PDF did not load" message={load.message}>
          <a
            href={props.url}
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-4 hover:text-foreground"
          >
            Open the original file
          </a>
        </ErrorState>
      </div>
    );
  }
  return <PdfPages pdf={load.pdf} pages={load.pages} {...props} />;
}
