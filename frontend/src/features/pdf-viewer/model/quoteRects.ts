import type { PdfRect } from './geometry';
import type { PDFPageProxy } from './pdfjs';

type TextContent = Awaited<ReturnType<PDFPageProxy['getTextContent']>>;
type TextItem = Extract<TextContent['items'][number], { str: string }>;

interface Glyph {
  item: number;
  offset: number;
}

interface Haystack {
  text: string;
  glyphs: Glyph[];
}

const SKIP = /[\s\u00ad]/;
const MIN_PREFIX = 24;

function normalizeChar(char: string): string {
  return char.normalize('NFKC').toLowerCase();
}

/** Lower-cased text without whitespace, with each char mapped to its item. */
function buildHaystack(items: readonly TextItem[]): Haystack {
  let text = '';
  const glyphs: Glyph[] = [];
  items.forEach((item, index) => {
    Array.from(item.str).forEach((char, offset) => {
      if (SKIP.test(char)) return;
      for (const piece of normalizeChar(char)) {
        text += piece;
        glyphs.push({ item: index, offset });
      }
    });
  });
  return { text, glyphs };
}

function needleOf(quote: string): string {
  return Array.from(quote)
    .filter((char) => !SKIP.test(char))
    .map(normalizeChar)
    .join('');
}

/** The full quote, else its first half, else a short prefix. */
function locate(text: string, needle: string): [number, number] | null {
  const candidates = [
    needle,
    needle.slice(0, Math.ceil(needle.length / 2)),
    needle.slice(0, MIN_PREFIX * 2),
  ];
  for (const candidate of candidates) {
    if (candidate.length < Math.min(MIN_PREFIX, needle.length)) continue;
    const start = text.indexOf(candidate);
    if (start >= 0) return [start, start + candidate.length - 1];
  }
  return null;
}

function itemRect(
  item: TextItem,
  [from, to]: [number, number],
  view: readonly number[],
): PdfRect {
  const [, , c = 0, d = 0, e = 0, f = 0] = item.transform as number[];
  const size = Math.hypot(c, d) || item.height;
  const length = Math.max(Array.from(item.str).length, 1);
  const x0 = e + (item.width * from) / length;
  const x1 = e + (item.width * (to + 1)) / length;
  const [left = 0, , , top = 0] = view;
  return [
    x0 - left,
    top - (f + size * 0.85),
    x1 - left,
    top - (f - size * 0.2),
  ];
}

/**
 * Finds `quote` in a page's text content and returns top-left-origin rects
 * (like PyMuPDF's) for the matched runs, or an empty list. Matching ignores
 * case and whitespace, because PDF text splits lines and words arbitrarily.
 */
export function findQuoteRects(
  content: TextContent,
  view: readonly number[],
  quote: string,
): PdfRect[] {
  const items = content.items.filter((item): item is TextItem => 'str' in item);
  const haystack = buildHaystack(items);
  const range = locate(haystack.text, needleOf(quote));
  if (!range) return [];
  const first = haystack.glyphs[range[0]];
  const last = haystack.glyphs[range[1]];
  if (!first || !last) return [];
  const rects: PdfRect[] = [];
  for (let index = first.item; index <= last.item; index += 1) {
    const item = items[index];
    if (!item || item.str.trim() === '') continue;
    const from = index === first.item ? first.offset : 0;
    const to =
      index === last.item ? last.offset : Array.from(item.str).length - 1;
    rects.push(itemRect(item, [from, to], view));
  }
  return rects;
}
