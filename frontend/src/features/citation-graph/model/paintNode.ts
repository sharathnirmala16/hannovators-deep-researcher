import { CATEGORY_STYLE, GRAPH_COLOR, type NodeShape } from './graphStyle';
import type { SourceNode } from './toGraphData';

/** How a node relates to the hovered or selected source. */
export type Emphasis = 'focus' | 'near' | 'dim' | 'rest';

interface NodePaint {
  emphasis: Emphasis;
  selected: boolean;
}

const HOLLOW: ReadonlySet<NodeShape> = new Set(['ring', 'dashed-ring']);

function tracePath(
  ctx: CanvasRenderingContext2D,
  shape: NodeShape,
  { x, y, r }: { x: number; y: number; r: number },
) {
  ctx.beginPath();
  if (shape === 'diamond') {
    const d = r * 1.2;
    ctx.moveTo(x, y - d);
    ctx.lineTo(x + d, y);
    ctx.lineTo(x, y + d);
    ctx.lineTo(x - d, y);
    ctx.closePath();
    return;
  }
  ctx.arc(x, y, r, 0, 2 * Math.PI);
}

function paintBody(
  ctx: CanvasRenderingContext2D,
  node: SourceNode,
  dim: boolean,
) {
  const style = CATEGORY_STYLE[node.category];
  const x = node.x ?? 0;
  const y = node.y ?? 0;
  const r = node.radius;
  const hollow = HOLLOW.has(style.shape);
  tracePath(ctx, style.shape, { x, y, r });
  ctx.fillStyle = hollow
    ? GRAPH_COLOR.paper
    : dim
      ? GRAPH_COLOR.dimFill
      : style.color;
  ctx.fill();
  ctx.setLineDash(style.shape === 'dashed-ring' ? [1.6, 1.4] : []);
  ctx.lineWidth = hollow ? 1.4 : 1;
  ctx.strokeStyle = hollow
    ? dim
      ? GRAPH_COLOR.dimStroke
      : style.color
    : GRAPH_COLOR.paper;
  ctx.stroke();
  ctx.setLineDash([]);
  if (style.shape === 'stamp') {
    ctx.beginPath();
    ctx.arc(x, y, r * 0.5, 0, 2 * Math.PI);
    ctx.lineWidth = 1.3;
    ctx.strokeStyle = GRAPH_COLOR.paper;
    ctx.stroke();
  }
}

/** The highlighter: a yellow disc behind the selected source. */
function paintHalo(ctx: CanvasRenderingContext2D, node: SourceNode) {
  ctx.beginPath();
  ctx.arc(node.x ?? 0, node.y ?? 0, node.radius + 5, 0, 2 * Math.PI);
  ctx.fillStyle = GRAPH_COLOR.marker;
  ctx.fill();
  ctx.lineWidth = 0.75;
  ctx.strokeStyle = GRAPH_COLOR.markerEdge;
  ctx.stroke();
}

function paintRing(ctx: CanvasRenderingContext2D, node: SourceNode) {
  ctx.beginPath();
  ctx.arc(node.x ?? 0, node.y ?? 0, node.radius + 2, 0, 2 * Math.PI);
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = GRAPH_COLOR.ink;
  ctx.stroke();
}

/** Draws one source: halo, body, then the focus ring. Labels come later. */
export function paintNode(
  ctx: CanvasRenderingContext2D,
  node: SourceNode,
  paint: NodePaint,
) {
  if (paint.selected) paintHalo(ctx, node);
  paintBody(ctx, node, paint.emphasis === 'dim' && !paint.selected);
  if (paint.emphasis === 'focus' || paint.selected) paintRing(ctx, node);
}

/** A hit area slightly larger than the body, for small hollow nodes. */
export function paintHitArea(
  ctx: CanvasRenderingContext2D,
  node: SourceNode,
  color: string,
) {
  ctx.beginPath();
  ctx.arc(node.x ?? 0, node.y ?? 0, node.radius + 3, 0, 2 * Math.PI);
  ctx.fillStyle = color;
  ctx.fill();
}
