import { useEffect, useState } from 'react';

import { errorMessage } from '@/shared/lib/format';

import type { PageGeometry } from './geometry';
import { openPdf, type PDFDocumentProxy } from './pdfjs';

export type PdfLoad =
  | { status: 'loading' }
  | { status: 'ready'; pdf: PDFDocumentProxy; pages: PageGeometry[] }
  | { status: 'error'; message: string };

const LOADING: PdfLoad = { status: 'loading' };

/** Every page's crop box and rotation, so placeholders have the real size. */
function readGeometry(pdf: PDFDocumentProxy): Promise<PageGeometry[]> {
  const numbers = Array.from({ length: pdf.numPages }, (_, index) => index + 1);
  return Promise.all(
    numbers.map(async (page) => {
      const proxy = await pdf.getPage(page);
      const [x0 = 0, y0 = 0, x1 = 0, y1 = 0] = proxy.view;
      return {
        page,
        viewWidth: Math.abs(x1 - x0),
        viewHeight: Math.abs(y1 - y0),
        rotation: (((proxy.rotate % 360) + 360) % 360) as number,
      };
    }),
  );
}

/** Loads the PDF at `url` with pdf.js and frees it when the URL changes. */
export function usePdfDocument(url: string): PdfLoad {
  const [current, setCurrent] = useState<{ url: string; load: PdfLoad }>();

  useEffect(() => {
    const task = openPdf(url);
    let cancelled = false;
    task.promise
      .then(async (pdf) => {
        const pages = await readGeometry(pdf);
        if (!cancelled)
          setCurrent({ url, load: { status: 'ready', pdf, pages } });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = errorMessage(error);
        setCurrent({ url, load: { status: 'error', message } });
      });
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [url]);

  return current?.url === url ? current.load : LOADING;
}
