import type { GraphView } from '@/domains/workspace';

import {
  CATEGORY_STYLE,
  nodeCategory,
  TIER_OF,
  type LinkKind,
  type NodeCategory,
  type Tier,
} from './graphStyle';
import { layoutOrbits, type Orbit } from './orbits';

export interface SourceNode {
  id: string;
  label: string;
  category: NodeCategory;
  radius: number;
  orbit: number;
  degree: number;
  /** Set by the force engine. */
  x?: number;
  y?: number;
}

export interface SourceLink {
  id: string;
  kind: LinkKind;
  /** An id until the force engine swaps in the node object. */
  source: string | SourceNode;
  target: string | SourceNode;
}

export interface SourceGraph {
  nodes: SourceNode[];
  links: SourceLink[];
  /** Node id to the ids of every node it links to, either way. */
  neighbours: ReadonlyMap<string, ReadonlySet<string>>;
  orbits: Orbit[];
}

/** The id at one end of a link, before or after the engine resolves it. */
export function endId(end: string | SourceNode): string {
  return typeof end === 'string' ? end : end.id;
}

function addNeighbour(map: Map<string, Set<string>>, a: string, b: string) {
  const set = map.get(a) ?? new Set<string>();
  set.add(b);
  map.set(a, set);
}

/**
 * Start angles: each tier's nodes evenly around its orbit, so the engine
 * only refines the layout instead of untangling a random one. The half step
 * keeps twelve o'clock free for the orbit's name.
 */
function evenPlacement(categories: readonly NodeCategory[]) {
  const totals = new Map<Tier, number>();
  for (const category of categories) {
    const tier = TIER_OF[category];
    totals.set(tier, (totals.get(tier) ?? 0) + 1);
  }
  const seen = new Map<Tier, number>();
  return (category: NodeCategory): number => {
    const tier = TIER_OF[category];
    const index = seen.get(tier) ?? 0;
    seen.set(tier, index + 1);
    return (
      -Math.PI / 2 + (2 * Math.PI * (index + 0.5)) / (totals.get(tier) ?? 1)
    );
  };
}

/** Graph nodes and links for the force engine; dangling edges are dropped. */
export function toGraphData(graph: GraphView): SourceGraph {
  const ids = new Set(graph.nodes.map((node) => node.id));
  const neighbours = new Map<string, Set<string>>();
  const links: SourceLink[] = graph.edges
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    .map((edge) => {
      addNeighbour(neighbours, edge.source, edge.target);
      addNeighbour(neighbours, edge.target, edge.source);
      return {
        id: `${edge.source}-${edge.target}-${edge.kind}`,
        kind: edge.kind,
        source: edge.source,
        target: edge.target,
      };
    });
  const categories = graph.nodes.map(nodeCategory);
  const { orbits, radiusOf } = layoutOrbits(categories);
  const place = evenPlacement(categories);
  const nodes = graph.nodes.map((node, index): SourceNode => {
    const category = categories[index] ?? 'other';
    const orbit = radiusOf(category);
    const angle = place(category);
    return {
      id: node.id,
      label: node.label,
      category,
      radius: CATEGORY_STYLE[category].radius,
      orbit,
      degree: neighbours.get(node.id)?.size ?? 0,
      x: orbit * Math.cos(angle),
      y: orbit * Math.sin(angle),
    };
  });
  return { nodes, links, neighbours, orbits };
}

/** Edges whose both ends are in the graph. */
export function linkCount(graph: GraphView): number {
  const ids = new Set(graph.nodes.map((node) => node.id));
  return graph.edges.filter(
    (edge) => ids.has(edge.source) && ids.has(edge.target),
  ).length;
}
