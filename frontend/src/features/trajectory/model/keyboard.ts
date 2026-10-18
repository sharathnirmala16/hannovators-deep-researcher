const MOVES: Record<string, (index: number, page: number) => number> = {
  ArrowDown: (index) => index + 1,
  ArrowUp: (index) => index - 1,
  PageDown: (index, page) => index + page,
  PageUp: (index, page) => index - page,
  Home: () => 0,
  End: () => Number.MAX_SAFE_INTEGER,
};

/**
 * Row index after a navigation key, clamped to the rows; null when the key
 * does not move the cursor. `index` is -1 when no row is active yet.
 */
export function moveCursor(
  key: string,
  index: number,
  count: number,
  page: number,
): number | null {
  const move = MOVES[key];
  if (!move || count === 0) return null;
  const from = index < 0 ? -1 : index;
  return Math.min(Math.max(move(from, page), 0), count - 1);
}
