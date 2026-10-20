import {
  GlobalWorkerOptions,
  RenderingCancelledException,
  getDocument,
  type PDFDocumentLoadingTask,
} from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = workerUrl;

export type {
  PDFDocumentProxy,
  PDFPageProxy,
  PageViewport,
  RenderTask,
} from 'pdfjs-dist';
export { TextLayer } from 'pdfjs-dist';

/** Starts loading a PDF; destroy the task to cancel it and free the worker. */
export function openPdf(url: string): PDFDocumentLoadingTask {
  return getDocument({ url });
}

/** pdf.js rejects cancelled renders; those are expected, not failures. */
export function isCancelled(error: unknown): boolean {
  return (
    error instanceof RenderingCancelledException ||
    (error instanceof Error && error.name === 'AbortException')
  );
}
