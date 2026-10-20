import { useEffect, useState } from 'react';

import type { PageRect } from './geometry';
import type { PDFDocumentProxy } from './pdfjs';
import { findQuoteRects } from './quoteRects';

const NONE: PageRect[] = [];

/** The named page first, then the rest in order. */
function pageOrder(count: number, page: number | null): number[] {
  const all = Array.from({ length: count }, (_, index) => index + 1);
  if (page === null || page < 1 || page > count) return all;
  return [page, ...all.filter((item) => item !== page)];
}

async function searchQuote(
  pdf: PDFDocumentProxy,
  page: number | null,
  quote: string,
  isStale: () => boolean,
): Promise<PageRect[]> {
  for (const number of pageOrder(pdf.numPages, page)) {
    if (isStale()) return NONE;
    const proxy = await pdf.getPage(number);
    const content = await proxy.getTextContent();
    const rects = findQuoteRects(content, proxy.view, quote);
    if (rects.length > 0) return rects.map((rect) => ({ page: number, rect }));
  }
  return NONE;
}

/**
 * When a selection has a quote but no rects, finds the quote in the PDF text
 * (the named page first) and returns rects for it. Pass a null quote to skip.
 */
export function useQuoteFallback(
  pdf: PDFDocumentProxy,
  page: number | null,
  quote: string | null,
): PageRect[] {
  const [found, setFound] = useState<{ key: string; rects: PageRect[] }>();
  const key = quote ? `${page ?? ''}|${quote}` : '';

  useEffect(() => {
    if (!quote) return undefined;
    let stale = false;
    searchQuote(pdf, page, quote, () => stale).then(
      (rects) => {
        if (!stale) setFound({ key, rects });
      },
      () => undefined,
    );
    return () => {
      stale = true;
    };
  }, [pdf, page, quote, key]);

  return key && found?.key === key ? found.rects : NONE;
}
