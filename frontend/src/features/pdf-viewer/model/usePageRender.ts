import { useEffect, useState, type RefObject } from 'react';

import {
  TextLayer,
  isCancelled,
  type PDFDocumentProxy,
  type PDFPageProxy,
  type PageViewport,
  type RenderTask,
} from './pdfjs';

/** Caps the canvas at this many device pixels (very high zoom stays light). */
const MAX_CANVAS_PIXELS = 16_777_216;

function outputScale(viewport: PageViewport): number {
  const ratio = window.devicePixelRatio || 1;
  const limit = Math.sqrt(
    MAX_CANVAS_PIXELS / Math.max(viewport.width * viewport.height, 1),
  );
  return Math.min(ratio, limit);
}

function createCanvas(viewport: PageViewport, ratio: number) {
  const canvas = document.createElement('canvas');
  canvas.width = Math.floor(viewport.width * ratio);
  canvas.height = Math.floor(viewport.height * ratio);
  canvas.style.display = 'block';
  canvas.style.width = '100%';
  canvas.style.height = '100%';
  return canvas;
}

interface PageRenderOptions {
  pdf: PDFDocumentProxy;
  pageNumber: number;
  scale: number;
  /** Only pages near the viewport render; far pages free their canvas. */
  near: boolean;
  canvasHost: RefObject<HTMLDivElement | null>;
  textHost: RefObject<HTMLDivElement | null>;
}

interface Hosts {
  canvasHost: HTMLDivElement;
  textHost: HTMLDivElement;
}

interface Running {
  cancelled: boolean;
  task: RenderTask | null;
  text: TextLayer | null;
}

/**
 * Draws into a fresh canvas and text layer, then swaps them in, so a re-render
 * at a new scale never shows a blank page (the old canvas stretches meanwhile).
 */
async function renderPage(
  page: PDFPageProxy,
  scale: number,
  hosts: Hosts,
  running: Running,
): Promise<boolean> {
  if (running.cancelled) return false;
  const viewport = page.getViewport({ scale });
  const ratio = outputScale(viewport);
  const canvas = createCanvas(viewport, ratio);
  const layer = document.createElement('div');
  layer.className = 'pdf-text-layer';
  running.task = page.render({
    canvas,
    viewport,
    ...(ratio === 1 ? {} : { transform: [ratio, 0, 0, ratio, 0, 0] }),
  });
  running.text = new TextLayer({
    textContentSource: page.streamTextContent(),
    container: layer,
    viewport,
  });
  await Promise.all([running.task.promise, running.text.render()]);
  if (running.cancelled) return false;
  hosts.canvasHost.replaceChildren(canvas);
  hosts.textHost.replaceChildren(layer);
  return true;
}

/** Renders one page's canvas and text layer; returns whether it is drawn. */
export function usePageRender({
  pdf,
  pageNumber,
  scale,
  near,
  canvasHost,
  textHost,
}: PageRenderOptions): boolean {
  const [drawn, setDrawn] = useState(false);

  useEffect(() => {
    const canvasElement = canvasHost.current;
    const textElement = textHost.current;
    if (!canvasElement || !textElement) return undefined;
    if (!near) {
      canvasElement.replaceChildren();
      textElement.replaceChildren();
      queueMicrotask(() => setDrawn(false));
      return undefined;
    }
    const hosts: Hosts = { canvasHost: canvasElement, textHost: textElement };
    const running: Running = { cancelled: false, task: null, text: null };
    pdf
      .getPage(pageNumber)
      .then((page) => renderPage(page, scale, hosts, running))
      .then(
        (done) => {
          if (done) setDrawn(true);
        },
        (error: unknown) => {
          if (!isCancelled(error) && !running.cancelled) console.warn(error);
        },
      );
    return () => {
      running.cancelled = true;
      running.task?.cancel();
      running.text?.cancel();
    };
  }, [pdf, pageNumber, scale, near, canvasHost, textHost]);

  return near && drawn;
}
