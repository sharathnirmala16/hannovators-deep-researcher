import type { SegmentOption } from '@/shared/ui/segmented';

export type DetailTab =
  'overview' | 'request' | 'response' | 'timing' | 'chain';

export const DETAIL_TABS: readonly SegmentOption<DetailTab>[] = [
  { value: 'overview', label: 'Overview' },
  { value: 'request', label: 'Request' },
  { value: 'response', label: 'Response' },
  { value: 'timing', label: 'Timing' },
  { value: 'chain', label: 'Chain' },
];
