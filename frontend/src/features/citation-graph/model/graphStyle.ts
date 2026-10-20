import type { StylesheetJson } from 'cytoscape';

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

/**
 * Cytoscape draws on a canvas and needs literal colors. These are the token
 * values from `index.css`; keep them in sync.
 */
export const GRAPH_COLOR = {
  ink: '#18223a',
  graphite: '#586378',
  paper: '#ffffff',
  edge: '#cdd5df', // shade-3
  edgeSeed: '#9aa5b5', // shade-4
  marker: '#ffe15a',
} as const;

export const CATEGORY_STYLE: Record<
  NodeCategory,
  { label: string; color: string; ring: number; size: number }
> = {
  seed: { label: 'Seed', color: '#2a4fa8', ring: 4, size: 28 }, // tone-info
  promoted: { label: 'Included', color: '#2e7552', ring: 3, size: 22 }, // tone-positive
  web: { label: 'Web', color: '#5e5a8c', ring: 2, size: 16 }, // tone-null
  discounted: {
    label: 'Screened out or excluded',
    color: '#9aa5b5',
    ring: 1,
    size: 13,
  }, // shade-4
  other: {
    label: 'Not yet appraised',
    color: '#cdd5df', // shade-3
    ring: 1,
    size: 11,
  },
};

export const LEGEND: readonly NodeCategory[] = [
  'seed',
  'promoted',
  'web',
  'discounted',
  'other',
];

const FONT =
  "'Atkinson Hyperlegible Next Variable', 'Segoe UI', Arial, sans-serif";

export const STYLESHEET: StylesheetJson = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      width: 'data(size)',
      height: 'data(size)',
      label: 'data(label)',
      'font-family': FONT,
      'font-size': 9,
      color: GRAPH_COLOR.ink,
      'text-valign': 'bottom',
      'text-margin-y': 3,
      'text-max-width': '96px',
      'text-wrap': 'ellipsis',
      'text-background-color': GRAPH_COLOR.paper,
      'text-background-opacity': 0.85,
      'text-background-padding': '1px',
      'border-width': 1,
      'border-color': GRAPH_COLOR.paper,
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 2,
      'border-color': GRAPH_COLOR.ink,
      'underlay-color': GRAPH_COLOR.marker,
      'underlay-padding': 5,
      'underlay-opacity': 1,
      'underlay-shape': 'ellipse',
      'font-weight': 'bold',
      'z-index': 10,
    },
  },
  {
    selector: 'edge',
    style: {
      width: 1,
      'line-color': GRAPH_COLOR.edge,
      'curve-style': 'bezier',
      'target-arrow-shape': 'triangle',
      'target-arrow-color': GRAPH_COLOR.edge,
      'arrow-scale': 0.6,
    },
  },
  { selector: 'edge.related', style: { 'line-style': 'dotted' } },
  {
    selector: 'edge.seed_match',
    style: {
      'line-style': 'dashed',
      'line-color': GRAPH_COLOR.edgeSeed,
      'target-arrow-color': GRAPH_COLOR.edgeSeed,
    },
  },
];
