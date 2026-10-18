import type { GraphNode } from '@/domains/workspace';

export type NodeCategory = 'seed' | 'promoted' | 'discounted' | 'web' | 'other';

/** Web origin wins over status, so every web page reads as web. */
export function nodeCategory(node: GraphNode): NodeCategory {
  if (node.status === 'SEED') return 'seed';
  if (node.origin === 'WEB') return 'web';
  if (node.status === 'APPRAISE_PROMOTED') return 'promoted';
  if (
    node.status === 'SCREEN_DISCOUNTED' ||
    node.status === 'APPRAISE_DISCOUNTED'
  ) {
    return 'discounted';
  }
  return 'other';
}

export const CATEGORY_STYLE: Record<
  NodeCategory,
  { label: string; color: string; ring: number; size: number }
> = {
  seed: { label: 'Seed', color: '#3730a3', ring: 4, size: 30 },
  promoted: { label: 'Promoted', color: '#15803d', ring: 3, size: 24 },
  web: { label: 'Web', color: '#0e7490', ring: 2, size: 16 },
  discounted: { label: 'Discounted', color: '#a8a29e', ring: 1, size: 14 },
  other: {
    label: 'Not screened or failed',
    color: '#e7e5e4',
    ring: 1,
    size: 12,
  },
};
