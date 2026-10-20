import { useCallback, useMemo, useState } from 'react';

import { GRAPH_COLOR, LINK_STYLE } from './graphStyle';
import { paintLabels } from './paintLabels';
import { paintNode, type Emphasis } from './paintNode';
import { paintOrbits } from './paintOrbits';
import {
  endId,
  type SourceGraph,
  type SourceLink,
  type SourceNode,
} from './toGraphData';

/**
 * The hovered source, else the selected one, is in focus: its links turn
 * graphite and everything outside its neighbourhood fades to solid grey.
 */
export function useGraphFocus(data: SourceGraph, selectedId: string | null) {
  const [hoverId, setHoverId] = useState<string | null>(null);
  const focusId = hoverId ?? selectedId;
  const near = focusId ? data.neighbours.get(focusId) : undefined;
  const focusNode = useMemo(
    () => data.nodes.find((node) => node.id === focusId) ?? null,
    [data, focusId],
  );

  // Only pointing fades the rest; a lasting selection keeps the graph readable.
  const fade = hoverId !== null;

  const emphasis = useCallback(
    (id: string): Emphasis => {
      if (!focusId) return 'rest';
      if (id === focusId) return 'focus';
      if (near?.has(id)) return 'near';
      return fade ? 'dim' : 'rest';
    },
    [focusId, near, fade],
  );

  const touchesFocus = useCallback(
    (link: SourceLink) =>
      endId(link.source) === focusId || endId(link.target) === focusId,
    [focusId],
  );

  const linkColor = useCallback(
    (link: SourceLink) => {
      if (focusId && touchesFocus(link)) return GRAPH_COLOR.graphite;
      return fade ? GRAPH_COLOR.dimFill : LINK_STYLE[link.kind].color;
    },
    [focusId, touchesFocus, fade],
  );

  const nodeCanvasObject = useCallback(
    (node: SourceNode, ctx: CanvasRenderingContext2D) =>
      paintNode(ctx, node, {
        emphasis: emphasis(node.id),
        selected: node.id === selectedId,
      }),
    [emphasis, selectedId],
  );

  const onRenderFramePre = useCallback(
    (ctx: CanvasRenderingContext2D, scale: number) =>
      paintOrbits(ctx, data.orbits, scale),
    [data],
  );

  const onRenderFramePost = useCallback(
    (ctx: CanvasRenderingContext2D, scale: number) =>
      paintLabels(ctx, data.nodes, { emphasis, selectedId, scale }),
    [data, emphasis, selectedId],
  );

  const linkWidth = useCallback(
    (link: SourceLink) => (focusId && touchesFocus(link) ? 1.6 : 1),
    [focusId, touchesFocus],
  );

  const onNodeHover = useCallback(
    (node: SourceNode | null) => setHoverId(node?.id ?? null),
    [],
  );

  return {
    focusNode,
    onNodeHover,
    nodeCanvasObject,
    onRenderFramePre,
    onRenderFramePost,
    linkColor,
    linkWidth,
    linkLineDash,
    linkArrowLength,
  };
}

function linkLineDash(link: SourceLink): number[] | null {
  return LINK_STYLE[link.kind].dash;
}

function linkArrowLength(link: SourceLink): number {
  return LINK_STYLE[link.kind].arrow ? 4 : 0;
}
