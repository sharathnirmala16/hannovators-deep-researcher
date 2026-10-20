import { CATEGORY_STYLE, FONT_FAMILY, GRAPH_COLOR } from './graphStyle';
import type { Emphasis } from './paintNode';
import type { SourceNode } from './toGraphData';

/** Minor nodes show their label from this zoom on. */
const LABEL_ZOOM = 2;
const LABEL_PX = 11;
const MAX_LABEL = 30;

const CATEGORY_RANK = { seed: 3, promoted: 4, web: 5, discounted: 6, other: 7 };

interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface LabelFrame {
  emphasis: (id: string) => Emphasis;
  selectedId: string | null;
  /** Canvas zoom: 1 is one graph unit per CSS pixel. */
  scale: number;
}

interface Candidate {
  node: SourceNode;
  emphasis: Emphasis;
  selected: boolean;
  /** Selected and focused labels always draw, even over others. */
  forced: boolean;
  rank: number;
}

function overlaps(a: Box, b: Box): boolean {
  return (
    a.left < b.left + b.width &&
    b.left < a.left + a.width &&
    a.top < b.top + b.height &&
    b.top < a.top + a.height
  );
}

function contains(outer: Box, inner: Box): boolean {
  return (
    inner.left >= outer.left &&
    inner.top >= outer.top &&
    inner.left + inner.width <= outer.left + outer.width &&
    inner.top + inner.height <= outer.top + outer.height
  );
}

/** The visible area in graph units, read back from the canvas transform. */
function viewBox(ctx: CanvasRenderingContext2D): Box {
  const inverse = ctx.getTransform().inverse();
  const a = inverse.transformPoint(new DOMPoint(0, 0));
  const b = inverse.transformPoint(
    new DOMPoint(ctx.canvas.width, ctx.canvas.height),
  );
  return { left: a.x, top: a.y, width: b.x - a.x, height: b.y - a.y };
}

function truncate(label: string): string {
  return label.length > MAX_LABEL ? `${label.slice(0, MAX_LABEL - 1)}…` : label;
}

function wanted(node: SourceNode, emphasis: Emphasis, scale: number): boolean {
  if (emphasis === 'focus' || emphasis === 'near') return true;
  if (emphasis === 'dim') return node.category === 'seed';
  return CATEGORY_STYLE[node.category].alwaysLabel || scale >= LABEL_ZOOM;
}

function toCandidate(node: SourceNode, frame: LabelFrame): Candidate | null {
  const emphasis = frame.emphasis(node.id);
  const selected = node.id === frame.selectedId;
  if (!selected && !wanted(node, emphasis, frame.scale)) return null;
  const forced = selected || emphasis === 'focus';
  const rank = selected
    ? 0
    : emphasis === 'focus'
      ? 1
      : emphasis === 'near'
        ? 2
        : CATEGORY_RANK[node.category];
  return { node, emphasis, selected, forced, rank };
}

/**
 * Places to try, best first: away from the center on the side, then above
 * or below on the outer side, then the remaining two.
 */
function placements(
  node: SourceNode,
  width: number,
  size: number,
  gap: number,
) {
  const x = node.x ?? 0;
  const y = node.y ?? 0;
  const r = node.radius + gap;
  const right = { left: x + r, top: y - size / 2, width, height: size };
  const left = { left: x - r - width, top: y - size / 2, width, height: size };
  const below = { left: x - width / 2, top: y + r, width, height: size };
  const above = { left: x - width / 2, top: y - r - size, width, height: size };
  const outerSide = x >= 0 ? right : left;
  const innerSide = x >= 0 ? left : right;
  const outerEnd = y >= 0 ? below : above;
  const innerEnd = y >= 0 ? above : below;
  return Math.abs(x) >= Math.abs(y) * 0.6
    ? [outerSide, outerEnd, innerEnd, innerSide]
    : [outerEnd, outerSide, innerSide, innerEnd];
}

function nodeBox(node: SourceNode): Box {
  const r = node.radius + 1;
  return {
    left: (node.x ?? 0) - r,
    top: (node.y ?? 0) - r,
    width: r * 2,
    height: r * 2,
  };
}

function labelColor(candidate: Candidate): string {
  if (candidate.emphasis === 'dim') return GRAPH_COLOR.dimLabel;
  const primary = CATEGORY_STYLE[candidate.node.category].alwaysLabel;
  return primary || candidate.emphasis !== 'rest'
    ? GRAPH_COLOR.ink
    : GRAPH_COLOR.graphite;
}

function drawLabel(
  ctx: CanvasRenderingContext2D,
  candidate: Candidate,
  { box, text, pad }: { box: Box; text: string; pad: number },
) {
  ctx.fillStyle = candidate.selected ? GRAPH_COLOR.marker : GRAPH_COLOR.canvas;
  ctx.beginPath();
  ctx.roundRect(
    box.left - pad,
    box.top - pad / 2,
    box.width + pad * 2,
    box.height + pad,
    pad,
  );
  ctx.fill();
  ctx.fillStyle = labelColor(candidate);
  ctx.fillText(text, box.left, box.top + box.height / 2);
}

/**
 * Labels in priority order, each at the first free place around its node.
 * A label that fits nowhere is skipped; hover or zoom brings it back.
 */
export function paintLabels(
  ctx: CanvasRenderingContext2D,
  nodes: readonly SourceNode[],
  frame: LabelFrame,
) {
  const candidates = nodes
    .map((node) => toCandidate(node, frame))
    .filter((candidate): candidate is Candidate => candidate !== null)
    .sort((a, b) => a.rank - b.rank);
  const size = LABEL_PX / frame.scale;
  const pad = 2 / frame.scale;
  const taken: Box[] = nodes.map(nodeBox);
  const view = viewBox(ctx);
  ctx.save();
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  for (const candidate of candidates) {
    const { node } = candidate;
    const weight = candidate.selected
      ? 700
      : node.category === 'seed'
        ? 600
        : 400;
    ctx.font = `${weight} ${size}px ${FONT_FAMILY}`;
    const text = truncate(node.label);
    const width = ctx.measureText(text).width;
    const options = placements(node, width, size, pad * 2).filter((box) =>
      contains(view, box),
    );
    const free = options.find(
      (box) => !taken.some((other) => overlaps(box, other)),
    );
    const box = free ?? (candidate.forced ? options[0] : undefined);
    if (!box) continue;
    taken.push({ ...box, left: box.left - pad, width: box.width + pad * 2 });
    drawLabel(ctx, candidate, { box, text, pad });
  }
  ctx.restore();
}
