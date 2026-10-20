import { forceCollide, forceRadial } from 'd3-force';
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from 'react';
import type {
  ForceGraphMethods,
  LinkObject,
  NodeObject,
} from 'react-force-graph-2d';

import { prefersReducedMotion } from './environment';
import type { SourceGraph, SourceLink, SourceNode } from './toGraphData';

export type GraphMethods = ForceGraphMethods<
  NodeObject<SourceNode>,
  LinkObject<SourceNode, SourceLink>
>;

const FIT_PADDING = 36;
const ZOOM_STEP = 1.4;
/** A node closer than this to the canvas edge is panned into view. */
const EDGE_MARGIN = 48;

/**
 * Each node is held on its tier's orbit; links only nudge it along the
 * orbit toward the sources it connects to.
 */
function configureForces(graph: GraphMethods) {
  graph.d3Force('center', null);
  graph.d3Force(
    'radial',
    forceRadial<SourceNode>((node) => node.orbit).strength((node) =>
      node.orbit === 0 ? 0.3 : 0.85,
    ),
  );
  graph.d3Force(
    'collide',
    forceCollide<SourceNode>((node) => node.radius + 9).iterations(2),
  );
  graph.d3Force('charge')?.strength(-40).distanceMax(160);
  graph.d3Force('link')?.distance(60).strength(0.03);
  graph.d3ReheatSimulation();
}

interface ForcesOptions {
  data: SourceGraph;
  /** The canvas has a size, so the graph is mounted. */
  ready: boolean;
  width: number;
  height: number;
}

interface GraphForces {
  ref: RefObject<GraphMethods | undefined>;
  controls: { zoomIn: () => void; zoomOut: () => void; fit: () => void };
  centerOn: (node: SourceNode) => void;
  onEngineStop: () => void;
  warmupTicks: number;
  cooldownTicks: number;
}

/** Forces, the one fit after the layout settles, and the zoom controls. */
export function useGraphForces({
  data,
  ready,
  width,
  height,
}: ForcesOptions): GraphForces {
  const ref = useRef<GraphMethods>(undefined);
  const fitted = useRef(false);
  const [reduced] = useState(prefersReducedMotion);
  const duration = reduced ? 0 : 400;

  useEffect(() => {
    const graph = ref.current;
    if (!ready || !graph) return;
    fitted.current = false;
    configureForces(graph);
  }, [data, ready]);

  useEffect(() => {
    if (fitted.current) ref.current?.zoomToFit(0, FIT_PADDING);
  }, [width, height]);

  const onEngineStop = useCallback(() => {
    if (fitted.current) return;
    fitted.current = true;
    ref.current?.zoomToFit(duration, FIT_PADDING);
  }, [duration]);

  const zoomBy = useCallback(
    (factor: number) => {
      const graph = ref.current;
      if (graph) graph.zoom(graph.zoom() * factor, duration / 2);
    },
    [duration],
  );

  const controls = useMemo(
    () => ({
      zoomIn: () => zoomBy(ZOOM_STEP),
      zoomOut: () => zoomBy(1 / ZOOM_STEP),
      fit: () => {
        ref.current?.zoomToFit(duration, FIT_PADDING);
      },
    }),
    [zoomBy, duration],
  );

  const centerOn = useCallback(
    (node: SourceNode) => {
      const graph = ref.current;
      if (!graph || node.x === undefined || node.y === undefined) return;
      const at = graph.graph2ScreenCoords(node.x, node.y);
      const m = EDGE_MARGIN;
      const inView =
        at.x >= m && at.y >= m && at.x <= width - m && at.y <= height - m;
      if (!inView) graph.centerAt(node.x, node.y, duration);
    },
    [duration, width, height],
  );

  return {
    ref,
    controls,
    centerOn,
    onEngineStop,
    /** Reduced motion paints the settled layout on the first frame. */
    warmupTicks: reduced ? 300 : 80,
    cooldownTicks: reduced ? 0 : 160,
  };
}
