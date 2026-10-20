import cytoscape, { type Core } from 'cytoscape';
import { useEffect, useRef } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import type { GraphView } from '@/domains/workspace';

import { STYLESHEET } from '../model/graphStyle';
import { toElements } from '../model/toElements';

interface GraphCanvasProps {
  graph: GraphView;
  /** Cytoscape failed to start (for example no canvas support). */
  onError: (error: unknown) => void;
}

/** The cytoscape canvas: concentric rings from seeds out; a tap opens a node. */
export function GraphCanvas({ graph, onError }: GraphCanvasProps) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const { selection, selectSource } = useEvidenceSelection();
  const onSelect = useRef(selectSource);
  const onFail = useRef(onError);
  const selectedId = selection.kind === 'none' ? null : selection.sourceId;

  useEffect(() => {
    onSelect.current = selectSource;
    onFail.current = onError;
  }, [selectSource, onError]);

  useEffect(() => {
    if (!container.current) return undefined;
    let cy: Core;
    try {
      cy = cytoscape({
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
    } catch (error) {
      onFail.current(error);
      return undefined;
    }
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
      aria-label="Citation graph of seeds, included, excluded, and web sources. Select a node to open the source."
      className="min-h-64 w-full flex-1 rounded-md bg-shade-0"
    />
  );
}
