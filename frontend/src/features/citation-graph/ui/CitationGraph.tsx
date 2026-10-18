import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import { useEffect, useRef } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import { useWorkspace, type GraphView } from '@/domains/workspace';

import {
  CATEGORY_STYLE,
  nodeCategory,
  type NodeCategory,
} from '../model/graphStyle';

function toElements(graph: GraphView): ElementDefinition[] {
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

const STYLESHEET: cytoscape.StylesheetJson = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      width: 'data(size)',
      height: 'data(size)',
      label: 'data(label)',
      'font-size': 9,
      color: '#44403c',
      'text-valign': 'bottom',
      'text-margin-y': 3,
      'text-max-width': '90px',
      'text-wrap': 'ellipsis',
      'border-width': 1,
      'border-color': '#ffffff',
    },
  },
  {
    selector: 'node:selected',
    style: { 'border-width': 3, 'border-color': '#ca8a04' },
  },
  {
    selector: 'edge',
    style: {
      width: 1,
      'line-color': '#d6d3d1',
      'curve-style': 'bezier',
      'target-arrow-shape': 'triangle',
      'target-arrow-color': '#d6d3d1',
      'arrow-scale': 0.6,
    },
  },
  { selector: 'edge.related', style: { 'line-style': 'dotted' } },
  {
    selector: 'edge.seed_match',
    style: {
      'line-style': 'dashed',
      'line-color': '#818cf8',
      'target-arrow-color': '#818cf8',
    },
  },
];

const LEGEND: NodeCategory[] = [
  'seed',
  'promoted',
  'web',
  'discounted',
  'other',
];

function GraphCanvas({ graph }: { graph: GraphView }) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const { selection, selectSource } = useEvidenceSelection();
  const onSelect = useRef(selectSource);
  const selectedId = selection.kind === 'none' ? null : selection.sourceId;

  useEffect(() => {
    onSelect.current = selectSource;
  }, [selectSource]);

  useEffect(() => {
    if (!container.current) return undefined;
    const cy = cytoscape({
      container: container.current,
      elements: toElements(graph),
      style: STYLESHEET,
      layout: {
        name: 'concentric',
        concentric: (node) => Number(node.data('ring')),
        levelWidth: () => 1,
        minNodeSpacing: 14,
        animate: false,
      },
      selectionType: 'single',
      wheelSensitivity: 0.3,
    });
    cy.on('tap', 'node', (event) => onSelect.current(event.target.id()));
    cyRef.current = cy;
    return () => {
      cyRef.current = null;
      cy.destroy();
    };
  }, [graph]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (selectedId) cy.getElementById(selectedId).select();
  }, [selectedId, graph]);

  return (
    <div
      ref={container}
      role="img"
      aria-label="Citation graph of seeds, promoted, discounted, and web sources"
      className="h-[26rem] w-full rounded-md bg-muted"
    />
  );
}

/** Cytoscape graph of how seeds connect to promoted, discounted, and web sources. */
export function CitationGraph() {
  const { load } = useWorkspace();
  if (load.status !== 'ready') return null;
  const { graph } = load;
  return (
    <section
      aria-labelledby="citation-graph-title"
      className="flex flex-col gap-2"
    >
      <header>
        <h2 id="citation-graph-title" className="text-base font-semibold">
          Citation graph
        </h2>
        <p className="text-xs text-muted-foreground">
          Click a node to open the source. Dashed lines join seeds to the
          studies they match; dotted lines are related articles.
        </p>
      </header>
      {graph.nodes.length === 0 ? (
        <div className="px-4 py-8 text-center text-sm text-muted-foreground">
          No sources yet. The graph fills in as the search finds and links
          sources.
        </div>
      ) : (
        <>
          <GraphCanvas graph={graph} />
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {LEGEND.map((category) => (
              <li key={category} className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden
                  className="size-2.5 rounded-full border border-border"
                  style={{ backgroundColor: CATEGORY_STYLE[category].color }}
                />
                {CATEGORY_STYLE[category].label}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
