import { memo, useRef, type CSSProperties } from 'react';

import { cn } from '@/shared/lib/cn';

import {
  pageCssSize,
  toCssBox,
  type PageGeometry,
  type PageRect,
} from '../model/geometry';
import type { PDFDocumentProxy } from '../model/pdfjs';
import { usePageRender } from '../model/usePageRender';

interface OverlayProps {
  geometry: PageGeometry;
  scale: number;
  active: readonly PageRect[];
  faint: readonly PageRect[];
}

/**
 * Highlight rectangles between the canvas and the text layer. The marker is
 * a solid color multiplied onto the page, so the print shows through.
 */
function HighlightOverlay({ geometry, scale, active, faint }: OverlayProps) {
  if (active.length === 0 && faint.length === 0) return null;
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      {faint.map(({ rect }, index) => (
        <span
          key={`faint-${index}`}
          data-highlight="faint"
          className="absolute border-b-2 border-marker"
          style={toCssBox(rect, geometry, scale)}
        />
      ))}
      {active.map(({ rect }, index) => (
        <span
          key={`active-${index}`}
          data-highlight="active"
          className="absolute rounded-[2px] bg-marker mix-blend-multiply"
          style={toCssBox(rect, geometry, scale)}
        />
      ))}
    </div>
  );
}

interface PdfPageProps extends OverlayProps {
  pdf: PDFDocumentProxy;
  near: boolean;
}

/** One page: a sized placeholder that draws itself near the viewport. */
export const PdfPage = memo(function PdfPage({
  pdf,
  geometry,
  scale,
  near,
  active,
  faint,
}: PdfPageProps) {
  const canvasHost = useRef<HTMLDivElement>(null);
  const textHost = useRef<HTMLDivElement>(null);
  const drawn = usePageRender({
    pdf,
    pageNumber: geometry.page,
    scale,
    near,
    canvasHost,
    textHost,
  });
  const size = pageCssSize(geometry, scale);
  const style = {
    width: size.width,
    height: size.height,
    '--total-scale-factor': scale,
    '--scale-round-x': '1px',
    '--scale-round-y': '1px',
  } as CSSProperties;

  return (
    <div
      data-page={geometry.page}
      role="region"
      aria-label={`Page ${geometry.page}`}
      className="relative isolate mx-auto shrink-0 overflow-hidden bg-background shadow-sm"
      style={style}
    >
      <div
        aria-hidden
        className={cn(
          'absolute inset-0 bg-muted',
          drawn ? 'hidden' : 'motion-safe:animate-pulse',
        )}
      />
      <div ref={canvasHost} className="absolute inset-0" />
      <HighlightOverlay
        geometry={geometry}
        scale={scale}
        active={active}
        faint={faint}
      />
      <div ref={textHost} className="absolute inset-0" />
    </div>
  );
});
