/**
 * GitHub-flavored pipe tables: a header row, an alignment row (`|---|:-:|`),
 * and body rows. Cells keep inline markdown and `[n]` citations; `\|` is a
 * literal pipe. Rows are padded or cut to the header width.
 */

import { parseInline, type Inline } from './markdownInline';

export type Align = 'left' | 'center' | 'right' | null;

export interface TableBlock {
  kind: 'table';
  align: Align[];
  header: Inline[][];
  rows: Inline[][][];
}

const DIVIDER_CELL = /^:?-+:?$/;

/** Splits a row on unescaped pipes, without the optional outer pipes. */
function splitRow(line: string): string[] {
  let row = line.trim();
  if (row.startsWith('|')) row = row.slice(1);
  if (row.endsWith('|') && !row.endsWith('\\|')) row = row.slice(0, -1);
  return row.split(/(?<!\\)\|/).map((cell) => cell.trim());
}

function dividerAlign(line: string): Align[] | null {
  if (!line.includes('-')) return null;
  const cells = splitRow(line);
  if (!cells.every((cell) => DIVIDER_CELL.test(cell))) return null;
  return cells.map((cell) => {
    const left = cell.startsWith(':');
    const right = cell.endsWith(':');
    if (left && right) return 'center';
    if (right) return 'right';
    return left ? 'left' : null;
  });
}

/** True when line `i` is a header row followed by an alignment row. */
export function isTableStart(lines: readonly string[], i: number): boolean {
  const header = lines[i] ?? '';
  const divider = lines[i + 1] ?? '';
  if (!header.includes('|') || !divider.includes('|')) return false;
  const align = dividerAlign(divider);
  return align !== null && align.length === splitRow(header).length;
}

function cells(line: string, width: number): Inline[][] {
  const values = splitRow(line);
  return Array.from({ length: width }, (_, index) =>
    parseInline((values[index] ?? '').replace(/\\\|/g, '|')),
  );
}

export function readTable(
  lines: readonly string[],
  i: number,
): [TableBlock, number] {
  const align = dividerAlign(lines[i + 1] ?? '') ?? [];
  const width = align.length;
  const rows: Inline[][][] = [];
  let j = i + 2;
  while (j < lines.length && (lines[j] ?? '').includes('|')) {
    rows.push(cells(lines[j] ?? '', width));
    j += 1;
  }
  const header = cells(lines[i] ?? '', width);
  return [{ kind: 'table', align, header, rows }, j];
}
