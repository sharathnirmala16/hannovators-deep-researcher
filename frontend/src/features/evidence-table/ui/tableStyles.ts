/**
 * A table inside the pane's one scroll area whose header row sticks to the
 * top. Borders are separate (on cells), so the header rule sticks with it.
 */
export const STICKY_TABLE =
  'table-fixed border-separate border-spacing-0 [&_td]:border-b [&_tbody_tr:last-child_td]:border-b-0';

export const STICKY_HEAD = 'sticky top-0 z-10 border-b bg-background';

/** The selected row: accent tint and an ink bar on the leading edge. */
export const SELECTED_ROW =
  'bg-accent hover:bg-accent data-[state=selected]:bg-accent [&>td:first-child]:shadow-[inset_2px_0_0_rgba(24,34,58,1)]';
