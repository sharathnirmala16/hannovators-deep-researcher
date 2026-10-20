import type { ElementDefinition } from 'cytoscape';

import type { GraphView } from '@/domains/workspace';

import { CATEGORY_STYLE, nodeCategory } from './graphStyle';

/** Graph nodes and edges as cytoscape elements; dangling edges are dropped. */
export function toElements(graph: GraphView): ElementDefinition[] {
  const ids = new Set(graph.nodes.map((node) => node.id));
  const nodes = graph.nodes.map((node) => {
    const style = CATEGORY_STYLE[nodeCategory(node)];
    return {
      data: {
        id: node.id,
        label: node.label,
        color: style.color,
        size: style.size,
        ring: style.ring,
      },
    };
  });
  const edges = graph.edges
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    .map((edge) => ({
      data: {
        id: `${edge.source}-${edge.target}-${edge.kind}`,
        source: edge.source,
        target: edge.target,
      },
      classes: edge.kind.toLowerCase(),
    }));
  return [...nodes, ...edges];
}

/** Edges whose both ends are in the graph. */
export function linkCount(graph: GraphView): number {
  const ids = new Set(graph.nodes.map((node) => node.id));
  return graph.edges.filter(
    (edge) => ids.has(edge.source) && ids.has(edge.target),
  ).length;
}
