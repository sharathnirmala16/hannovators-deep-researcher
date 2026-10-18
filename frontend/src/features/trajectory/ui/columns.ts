/**
 * Table columns. Optional columns hide by the table's own width (container
 * queries), so the table stays readable when the detail panel is open.
 */
export const COLUMN = {
  index: 'w-14 text-right',
  time: 'hidden w-20 text-right @3xl:table-cell',
  actor: 'hidden w-16 @4xl:table-cell',
  kind: 'w-28',
  name: 'w-[26%]',
  target: 'hidden @2xl:table-cell',
  status: 'w-20',
  outcome: 'hidden w-20 @xl:table-cell',
  confidence: 'hidden w-14 text-right @4xl:table-cell',
  duration: 'hidden w-20 text-right @lg:table-cell',
  waterfall: 'hidden w-44 @5xl:table-cell',
} as const;

export const COLUMN_COUNT = Object.keys(COLUMN).length;

/** Fixed row height in px; the windowing math depends on it. */
export const ROW_HEIGHT = 28;
export const HEADER_HEIGHT = 30;

export const stepRowId = (id: number) => `trajectory-step-${id}`;
