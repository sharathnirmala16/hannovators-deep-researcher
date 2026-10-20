import { useEffect, useMemo, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

import { useEvidenceSelection } from '@/domains/evidence';
import type { GraphView } from '@/domains/workspace';

import { useElementSize } from '../model/environment';
import { paintHitArea } from '../model/paintNode';
import {
  toGraphData,
  type SourceLink,
  type SourceNode,
} from '../model/toGraphData';
import { useGraphFocus } from '../model/useGraphFocus';
import { useGraphForces } from '../model/useGraphForces';
import { GraphControls } from './GraphControls';
import { GraphReadout } from './GraphReadout';

/** The force canvas: tiers on orbits around the seeds; a click opens a node. */
export function GraphCanvas({ graph }: { graph: GraphView }) {
  const data = useMemo(() => toGraphData(graph), [graph]);
  const [box, { width, height }] = useElementSize<HTMLDivElement>();
  const ready = width > 0 && height > 0;
  const { selection, selectSource } = useEvidenceSelection();
  const selectedId = selection.kind === 'none' ? null : selection.sourceId;
  const { ref, controls, centerOn, onEngineStop, warmupTicks, cooldownTicks } =
    useGraphForces({ data, ready, width, height });
  const focus = useGraphFocus(data, selectedId);
  const clicked = useRef<string | null>(null);

  // A source picked in another pane is panned into view when off screen.
  useEffect(() => {
    const fromCanvas = selectedId === clicked.current;
    clicked.current = null;
    if (!selectedId || fromCanvas) return;
    const node = data.nodes.find((item) => item.id === selectedId);
    if (node) centerOn(node);
  }, [selectedId, data, centerOn]);

  return (
    <div
      ref={box}
      role="img"
      aria-label="Citation graph. Seeds sit at the center, included sources on the first ring, web and excluded sources further out. Select a node to open the source."
      className="relative min-h-64 w-full flex-1 overflow-hidden rounded-md bg-shade-0"
    >
      {ready ? (
        <ForceGraph2D<SourceNode, SourceLink>
          ref={ref}
          width={width}
          height={height}
          graphData={data}
          backgroundColor="#f8fafc"
          nodeId="id"
          nodeVal={(node) => node.radius * node.radius}
          nodeRelSize={1}
          nodeLabel={() => ''}
          nodeCanvasObject={focus.nodeCanvasObject}
          nodePointerAreaPaint={(node, color, ctx) =>
            paintHitArea(ctx, node, color)
          }
          linkColor={focus.linkColor}
          linkWidth={focus.linkWidth}
          linkLineDash={focus.linkLineDash}
          linkDirectionalArrowLength={focus.linkArrowLength}
          linkDirectionalArrowRelPos={1}
          linkDirectionalArrowColor={focus.linkColor}
          linkHoverPrecision={0}
          onRenderFramePre={focus.onRenderFramePre}
          onRenderFramePost={focus.onRenderFramePost}
          onNodeHover={focus.onNodeHover}
          onNodeClick={(node) => {
            clicked.current = node.id;
            selectSource(node.id);
          }}
          onEngineStop={onEngineStop}
          warmupTicks={warmupTicks}
          cooldownTicks={cooldownTicks}
          minZoom={0.3}
          maxZoom={8}
        />
      ) : null}
      <GraphControls {...controls} />
      {focus.focusNode ? <GraphReadout node={focus.focusNode} /> : null}
    </div>
  );
}
