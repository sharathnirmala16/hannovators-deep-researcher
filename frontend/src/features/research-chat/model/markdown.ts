/**
 * A small, safe markdown subset for chat answers: paragraphs, bullet and
 * numbered lists, headings (rendered as strong paragraphs), **bold**,
 * *italic*, `code`, and `[n]` citation markers. It returns a tree that the UI
 * renders as React elements, so no HTML string is ever injected.
 */

export type Inline =
  | { kind: 'text'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'strong'; children: Inline[] }
  | { kind: 'em'; children: Inline[] }
  | { kind: 'cite'; n: number };

export type Block =
  | { kind: 'paragraph'; inlines: Inline[] }
  | { kind: 'heading'; inlines: Inline[] }
  | { kind: 'list'; ordered: boolean; start: number; items: Inline[][] };

const INLINE =
  /`([^`]+)`|\*\*(.+?)\*\*|__(.+?)__|\*([^*\s](?:[^*]*[^*\s])?)\*|\b_([^_\s](?:[^_]*[^_\s])?)_\b|\[(\d+(?:\s*[,;]\s*\d+)*)\]/g;

function citations(group: string): Inline[] {
  return group
    .split(/[,;]/)
    .map((part) => ({ kind: 'cite', n: Number(part.trim()) }) as const);
}

function inlineToken(match: RegExpMatchArray): Inline[] {
  const [, code, bold, boldAlt, em, emAlt, cites] = match;
  if (code !== undefined) return [{ kind: 'code', text: code }];
  const strong = bold ?? boldAlt;
  if (strong !== undefined) {
    return [{ kind: 'strong', children: parseInline(strong) }];
  }
  const italic = em ?? emAlt;
  if (italic !== undefined) {
    return [{ kind: 'em', children: parseInline(italic) }];
  }
  return citations(cites ?? '');
}

function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let cursor = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > cursor) {
      out.push({ kind: 'text', text: text.slice(cursor, match.index) });
    }
    out.push(...inlineToken(match));
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length)
    out.push({ kind: 'text', text: text.slice(cursor) });
  return out;
}

const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;

type LineKind =
  | { kind: 'blank' }
  | { kind: 'heading'; text: string }
  | { kind: 'item'; ordered: boolean; start: number; text: string }
  | { kind: 'text'; text: string; indented: boolean };

function classify(line: string): LineKind {
  if (line.trim() === '') return { kind: 'blank' };
  const heading = HEADING.exec(line);
  if (heading) return { kind: 'heading', text: heading[1] ?? '' };
  const bullet = BULLET.exec(line);
  if (bullet) {
    return { kind: 'item', ordered: false, start: 1, text: bullet[1] ?? '' };
  }
  const numbered = NUMBERED.exec(line);
  if (numbered) {
    const start = Number(numbered[1]);
    return { kind: 'item', ordered: true, start, text: numbered[2] ?? '' };
  }
  return { kind: 'text', text: line.trim(), indented: /^\s{2,}/.test(line) };
}

interface Draft {
  blocks: Block[];
  paragraph: string[];
  list: { ordered: boolean; start: number; items: string[] } | null;
}

function flush(draft: Draft): void {
  if (draft.paragraph.length > 0) {
    const inlines = parseInline(draft.paragraph.join(' '));
    draft.blocks.push({ kind: 'paragraph', inlines });
    draft.paragraph = [];
  }
  if (draft.list) {
    const { ordered, start, items } = draft.list;
    draft.blocks.push({
      kind: 'list',
      ordered,
      start,
      items: items.map(parseInline),
    });
    draft.list = null;
  }
}

function addItem(draft: Draft, line: Extract<LineKind, { kind: 'item' }>) {
  if (draft.list?.ordered !== line.ordered) flush(draft);
  if (draft.paragraph.length > 0) flush(draft);
  draft.list ??= { ordered: line.ordered, start: line.start, items: [] };
  draft.list.items.push(line.text);
}

function addText(draft: Draft, line: Extract<LineKind, { kind: 'text' }>) {
  const items = draft.list?.items;
  if (items && items.length > 0 && line.indented) {
    items[items.length - 1] = `${items[items.length - 1]} ${line.text}`;
    return;
  }
  if (draft.list) flush(draft);
  draft.paragraph.push(line.text);
}

function addLine(draft: Draft, line: LineKind): void {
  switch (line.kind) {
    case 'blank':
      flush(draft);
      return;
    case 'heading':
      flush(draft);
      draft.blocks.push({ kind: 'heading', inlines: parseInline(line.text) });
      return;
    case 'item':
      addItem(draft, line);
      return;
    case 'text':
      addText(draft, line);
  }
}

export function parseMarkdown(content: string): Block[] {
  const draft: Draft = { blocks: [], paragraph: [], list: null };
  for (const line of content.replace(/\r\n?/g, '\n').split('\n')) {
    addLine(draft, classify(line));
  }
  flush(draft);
  return draft.blocks;
}
