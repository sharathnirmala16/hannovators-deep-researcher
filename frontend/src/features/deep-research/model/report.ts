export type Inline =
  { kind: 'text'; text: string } | { kind: 'cite'; n: number };

export type Block =
  | { kind: 'heading'; inline: Inline[] }
  | { kind: 'item'; inline: Inline[] }
  | { kind: 'paragraph'; inline: Inline[] };

const CITE = /\[(\d{1,3})\]/g;

/** Splits text around `[n]` markers and drops markdown emphasis marks. */
export function parseInline(text: string): Inline[] {
  const clean = text.replace(/\*\*|__/g, '');
  const parts: Inline[] = [];
  let cursor = 0;
  for (const match of clean.matchAll(CITE)) {
    if (match.index > cursor) {
      parts.push({ kind: 'text', text: clean.slice(cursor, match.index) });
    }
    parts.push({ kind: 'cite', n: Number(match[1]) });
    cursor = match.index + match[0].length;
  }
  if (cursor < clean.length) {
    parts.push({ kind: 'text', text: clean.slice(cursor) });
  }
  return parts;
}

const HEADING = /^#{1,6}\s+/;
const ITEM = /^\s*(?:[-*+]|\d+\.)\s+/;

/** A small markdown subset: headings, list items, and paragraphs. */
export function parseReport(content: string): Block[] {
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  const flush = () => {
    if (paragraph.length === 0) return;
    blocks.push({
      kind: 'paragraph',
      inline: parseInline(paragraph.join(' ')),
    });
    paragraph = [];
  };
  for (const line of content.split(/\r?\n/)) {
    if (!line.trim()) {
      flush();
    } else if (HEADING.test(line)) {
      flush();
      blocks.push({
        kind: 'heading',
        inline: parseInline(line.replace(HEADING, '')),
      });
    } else if (ITEM.test(line)) {
      flush();
      blocks.push({
        kind: 'item',
        inline: parseInline(line.replace(ITEM, '')),
      });
    } else {
      paragraph.push(line.trim());
    }
  }
  flush();
  return blocks;
}
