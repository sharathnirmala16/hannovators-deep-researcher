/**
 * A safe GitHub-flavored markdown subset for reports, chat answers, and web
 * snapshots: ATX and setext headings, paragraphs, ordered and unordered lists
 * (nested by indentation), blockquotes, horizontal rules, fenced code, and
 * pipe tables with an alignment row. Inline syntax is in `markdownInline.ts`.
 * The result is a tree the UI renders as React elements, so no HTML string is
 * ever injected.
 */

import { parseInline, type Inline } from './markdownInline';
import {
  isTableStart,
  readTable,
  type Align,
  type TableBlock,
} from './markdownTable';

export type { Align, Inline };

export type Block =
  | { kind: 'heading'; level: number; inlines: Inline[] }
  | { kind: 'paragraph'; inlines: Inline[] }
  | { kind: 'list'; ordered: boolean; start: number; items: Block[][] }
  | { kind: 'quote'; blocks: Block[] }
  | { kind: 'rule' }
  | { kind: 'code'; text: string }
  | TableBlock;

const HEADING = /^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$/;
const SETEXT = /^ {0,3}(=+|-+)\s*$/;
const RULE = /^ {0,3}([-*_])(?:\s*\1){2,}\s*$/;
const FENCE = /^ {0,3}(`{3,}|~{3,})/;
const QUOTE = /^ {0,3}>\s?(.*)$/;
const MARKER = /^(\s*)(?:([-*+])|(\d{1,9})[.)])(\s+|$)(.*)$/;

interface Marker {
  ordered: boolean;
  start: number;
  indent: number;
  /** Lines indented at least this much belong to the item. */
  inner: number;
  text: string;
}

const indentOf = (line: string) => line.length - line.trimStart().length;
const isBlank = (line: string | undefined) => !line?.trim();

function marker(line: string): Marker | null {
  const match = MARKER.exec(line);
  if (!match || RULE.test(line)) return null;
  const [, lead = '', bullet, digits, gap = '', text = ''] = match;
  const indent = lead.length;
  const offset = indent + (bullet ?? `${digits}.`).length + gap.length;
  return {
    ordered: bullet === undefined,
    start: digits === undefined ? 1 : Number(digits),
    indent,
    inner: Math.min(offset, indent + 2),
    text,
  };
}

function startsBlock(lines: readonly string[], i: number): boolean {
  const line = lines[i] ?? '';
  return (
    HEADING.test(line) ||
    RULE.test(line) ||
    FENCE.test(line) ||
    QUOTE.test(line) ||
    marker(line) !== null ||
    isTableStart(lines, i)
  );
}

type Reader = (lines: readonly string[], i: number) => [Block, number];

function readFence(lines: readonly string[], i: number): [Block, number] {
  const fence = FENCE.exec(lines[i] ?? '')?.[1] ?? '```';
  const body: string[] = [];
  let j = i + 1;
  while (j < lines.length && !(lines[j] ?? '').trim().startsWith(fence)) {
    body.push(lines[j] ?? '');
    j += 1;
  }
  return [{ kind: 'code', text: body.join('\n') }, j + 1];
}

function readQuote(lines: readonly string[], i: number): [Block, number] {
  const body: string[] = [];
  let j = i;
  for (; j < lines.length; j += 1) {
    const match = QUOTE.exec(lines[j] ?? '');
    if (!match) break;
    body.push(match[1] ?? '');
  }
  return [{ kind: 'quote', blocks: parseLines(body) }, j];
}

/** The lines of one list item (dedented), and the index after it. */
function readItem(
  lines: readonly string[],
  i: number,
  item: Marker,
): [string[], number] {
  const body = [item.text];
  let j = i + 1;
  while (j < lines.length) {
    const line = lines[j] ?? '';
    if (isBlank(line)) {
      let k = j;
      while (k < lines.length && isBlank(lines[k])) k += 1;
      if (k >= lines.length || indentOf(lines[k] ?? '') < item.inner) break;
      body.push(...lines.slice(j, k).map(() => ''));
      j = k;
    } else if (indentOf(line) >= item.inner) {
      body.push(line.slice(item.inner));
      j += 1;
    } else if (startsBlock(lines, j)) {
      break;
    } else {
      body.push(line.trim());
      j += 1;
    }
  }
  return [body, j];
}

function nextSibling(
  lines: readonly string[],
  j: number,
  first: Marker,
): number | null {
  let k = j;
  while (k < lines.length && isBlank(lines[k])) k += 1;
  const next = marker(lines[k] ?? '');
  const sibling =
    next !== null &&
    next.ordered === first.ordered &&
    next.indent < first.inner &&
    k - j <= 1;
  return sibling ? k : null;
}

function readList(lines: readonly string[], i: number): [Block, number] {
  const first = marker(lines[i] ?? '') as Marker;
  const items: Block[][] = [];
  let j: number | null = i;
  let end = i;
  while (j !== null) {
    const item = marker(lines[j] ?? '') as Marker;
    const [body, after] = readItem(lines, j, item);
    items.push(parseLines(body));
    end = after;
    j = nextSibling(lines, after, first);
  }
  const block: Block = {
    kind: 'list',
    ordered: first.ordered,
    start: first.start,
    items,
  };
  return [block, end];
}

function readParagraph(lines: readonly string[], i: number): [Block, number] {
  const body = [(lines[i] ?? '').trim()];
  let j = i + 1;
  while (j < lines.length && !isBlank(lines[j])) {
    const setext = SETEXT.exec(lines[j] ?? '');
    if (setext) {
      const level = setext[1]?.startsWith('=') ? 1 : 2;
      const inlines = parseInline(body.join(' '));
      return [{ kind: 'heading', level, inlines }, j + 1];
    }
    if (startsBlock(lines, j)) break;
    body.push((lines[j] ?? '').trim());
    j += 1;
  }
  return [{ kind: 'paragraph', inlines: parseInline(body.join(' ')) }, j];
}

function readHeading(lines: readonly string[], i: number): [Block, number] {
  const match = HEADING.exec(lines[i] ?? '');
  const level = match?.[1]?.length ?? 1;
  return [
    { kind: 'heading', level, inlines: parseInline(match?.[2] ?? '') },
    i + 1,
  ];
}

function readerFor(lines: readonly string[], i: number): Reader {
  const line = lines[i] ?? '';
  if (FENCE.test(line)) return readFence;
  if (HEADING.test(line)) return readHeading;
  if (RULE.test(line)) return (_, at) => [{ kind: 'rule' }, at + 1];
  if (QUOTE.test(line)) return readQuote;
  if (isTableStart(lines, i)) return readTable;
  if (marker(line)) return readList;
  return readParagraph;
}

function parseLines(lines: readonly string[]): Block[] {
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    if (isBlank(lines[i])) {
      i += 1;
      continue;
    }
    const [block, next] = readerFor(lines, i)(lines, i);
    if (!isEmpty(block)) blocks.push(block);
    i = Math.max(next, i + 1);
  }
  return blocks;
}

/** A paragraph left empty after images were dropped is not shown. */
function isEmpty(block: Block): boolean {
  return (
    block.kind === 'paragraph' &&
    block.inlines.every(
      (inline) => inline.kind === 'text' && !inline.text.trim(),
    )
  );
}

export function parseMarkdown(content: string): Block[] {
  return parseLines(
    content.replace(/\r\n?/g, '\n').replace(/\t/g, '    ').split('\n'),
  );
}

function inlineRuns(inlines: readonly Inline[]): string[] {
  return inlines.flatMap((inline) => {
    if (inline.kind === 'text') return [inline.text];
    if (inline.kind === 'code' || inline.kind === 'cite') return [];
    return inlineRuns(inline.children);
  });
}

function blockRuns(block: Block): string[] {
  switch (block.kind) {
    case 'heading':
    case 'paragraph':
      return inlineRuns(block.inlines);
    case 'list':
      return block.items.flatMap((item) => item.flatMap(blockRuns));
    case 'quote':
      return block.blocks.flatMap(blockRuns);
    case 'table':
      return [...block.header, ...block.rows.flat()].flatMap(inlineRuns);
    default:
      return [];
  }
}

/** Every plain text run the renderer passes to a `text` renderer. */
export function textRuns(blocks: readonly Block[]): string[] {
  return blocks.flatMap(blockRuns);
}
