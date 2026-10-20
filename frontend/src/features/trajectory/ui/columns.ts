/**
 * Table columns. Optional columns hide by the table's own width (container
 * queries), so the table stays readable when the detail panel is open.
 */
export const COLUMN = {
  index: 'w-12 text-right',
  time: 'hidden w-24 text-right @2xl:table-cell',
  actor: 'hidden w-16 @4xl:table-cell',
  kind: 'w-28',
  name: 'w-[22%]',
  target: 'hidden @3xl:table-cell',
  status: 'w-20',
  outcome: 'hidden w-20 @xl:table-cell',
  confidence: 'hidden w-24 text-right @4xl:table-cell',
  duration: 'hidden w-20 text-right @lg:table-cell',
  waterfall: 'hidden w-44 @5xl:table-cell',
} as const;

export const HEADERS: readonly (readonly [keyof typeof COLUMN, string])[] = [
  ['index', '#'],
  ['time', 'Since start'],
  ['actor', 'Actor'],
  ['kind', 'Kind'],
  ['name', 'Name'],
  ['target', 'Target'],
  ['status', 'Status'],
  ['outcome', 'Outcome'],
  ['confidence', 'Confidence'],
  ['duration', 'Duration'],
  ['waterfall', 'Waterfall'],
];

/** Fixed row height in px; the windowing math depends on it. */
export const ROW_HEIGHT = 32;
export const HEADER_HEIGHT = 32;

/** The row hairline, drawn as an inset shadow so it never adds height. */
export const HAIRLINE = 'shadow-[inset_0_-1px_0_var(--color-border)]';

export const stepRowId = (id: number) => `trajectory-step-${id}`;
