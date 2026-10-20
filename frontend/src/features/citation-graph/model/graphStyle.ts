import type { GraphEdge, GraphNode } from '@/domains/workspace';
import type { Tone } from '@/shared/ui/tag';

export type NodeCategory = 'seed' | 'promoted' | 'discounted' | 'web' | 'other';
export type LinkKind = GraphEdge['kind'];

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

/**
 * The canvas needs literal colors. These are the token values from
 * `index.css`; keep them in sync.
 */
export const GRAPH_COLOR = {
  ink: '#18223a',
  graphite: '#586378',
  paper: '#ffffff',
  canvas: '#f8fafc', // shade-0, the graph's background
  marker: '#ffe15a',
  markerEdge: '#e6c63a',
  orbit: '#e3e8ef', // shade-2
  orbitLabel: '#9aa5b5', // shade-4
  dimFill: '#e3e8ef', // shade-2
  dimStroke: '#cdd5df', // shade-3
  dimLabel: '#9aa5b5', // shade-4
} as const;

export const FONT_FAMILY =
  "'Atkinson Hyperlegible Next Variable', 'Segoe UI', Arial, sans-serif";

export type NodeShape = 'stamp' | 'disc' | 'diamond' | 'ring' | 'dashed-ring';

interface CategoryStyle {
  label: string;
  /** Fill for solid shapes, stroke for hollow ones. */
  color: string;
  shape: NodeShape;
  radius: number;
  tone: Tone;
  /** Labels always show for the categories a reader scans for. */
  alwaysLabel: boolean;
}

export const CATEGORY_STYLE: Record<NodeCategory, CategoryStyle> = {
  seed: {
    label: 'Seed',
    color: '#2a4fa8', // tone-info
    shape: 'stamp',
    radius: 8,
    tone: 'info',
    alwaysLabel: true,
  },
  promoted: {
    label: 'Included',
    color: '#2e7552', // tone-positive
    shape: 'disc',
    radius: 6,
    tone: 'positive',
    alwaysLabel: true,
  },
  web: {
    label: 'Web',
    color: '#5e5a8c', // tone-null
    shape: 'diamond',
    radius: 5,
    tone: 'null',
    alwaysLabel: false,
  },
  discounted: {
    label: 'Screened out or excluded',
    color: '#9aa5b5', // shade-4
    shape: 'ring',
    radius: 4.5,
    tone: 'negative',
    alwaysLabel: false,
  },
  other: {
    label: 'Not yet appraised',
    color: '#9aa5b5', // shade-4
    shape: 'dashed-ring',
    radius: 4,
    tone: 'neutral',
    alwaysLabel: false,
  },
};

export const LEGEND: readonly NodeCategory[] = [
  'seed',
  'promoted',
  'web',
  'discounted',
  'other',
];

/** Evidence tiers: seeds hold the core, every other tier one orbit. */
export type Tier = 'core' | 'included' | 'web' | 'outer';
export type OrbitTier = Exclude<Tier, 'core'>;

export const TIER_OF: Record<NodeCategory, Tier> = {
  seed: 'core',
  promoted: 'included',
  web: 'web',
  discounted: 'outer',
  other: 'outer',
};

/** Inner to outer. `spacing` is the arc length each node needs. */
export const ORBIT_TIERS: readonly {
  tier: OrbitTier;
  label: string;
  minRadius: number;
  spacing: number;
  dashed: boolean;
}[] = [
  {
    tier: 'included',
    label: 'Included',
    minRadius: 90,
    spacing: 44,
    dashed: false,
  },
  { tier: 'web', label: 'Web', minRadius: 150, spacing: 30, dashed: false },
  {
    tier: 'outer',
    label: 'Not included',
    minRadius: 200,
    spacing: 24,
    dashed: true,
  },
];

/** The least gap between two neighbouring orbits. */
export const ORBIT_GAP = 64;

export const LINK_STYLE: Record<
  LinkKind,
  { label: string; color: string; dash: number[] | null; arrow: boolean }
> = {
  CITES: { label: 'Cites', color: '#cdd5df', dash: null, arrow: true },
  SEED_MATCH: {
    label: 'Seed match',
    color: '#9aa5b5',
    dash: [4, 3],
    arrow: false,
  },
  RELATED: {
    label: 'Related article',
    color: '#cdd5df',
    dash: [1, 2.5],
    arrow: false,
  },
};

export const LINK_LEGEND: readonly LinkKind[] = [
  'CITES',
  'SEED_MATCH',
  'RELATED',
];
