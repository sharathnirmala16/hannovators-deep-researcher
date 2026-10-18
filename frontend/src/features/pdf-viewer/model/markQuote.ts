export interface TextSegment {
  text: string;
  marked: boolean;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Splits `text` around every match of `quote`. The match ignores case and
 * treats any run of whitespace as equal, because snapshots re-wrap lines.
 */
export function markQuote(text: string, quote: string | null): TextSegment[] {
  const words = quote?.trim().split(/\s+/).filter(Boolean) ?? [];
  if (words.length === 0 || text.length === 0) {
    return text.length === 0 ? [] : [{ text, marked: false }];
  }
  const pattern = new RegExp(words.map(escapeRegExp).join('\\s+'), 'gi');
  const segments: TextSegment[] = [];
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) {
      segments.push({ text: text.slice(cursor, match.index), marked: false });
    }
    segments.push({ text: match[0], marked: true });
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), marked: false });
  }
  return segments;
}
