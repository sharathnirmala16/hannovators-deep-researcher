import { FONT_FAMILY, GRAPH_COLOR } from './graphStyle';
import type { Orbit } from './orbits';

const ORBIT_LABEL_PX = 10;

/** Hairline tier guides with their name at the top, under every node. */
export function paintOrbits(
  ctx: CanvasRenderingContext2D,
  orbits: readonly Orbit[],
  scale: number,
) {
  const unit = 1 / scale;
  ctx.save();
  ctx.lineWidth = unit;
  ctx.strokeStyle = GRAPH_COLOR.orbit;
  ctx.font = `500 ${ORBIT_LABEL_PX * unit}px ${FONT_FAMILY}`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'bottom';
  for (const { label, radius, dashed } of orbits) {
    ctx.setLineDash(dashed ? [4 * unit, 4 * unit] : []);
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, 2 * Math.PI);
    ctx.stroke();
    const width = ctx.measureText(label).width;
    ctx.fillStyle = GRAPH_COLOR.canvas;
    ctx.fillRect(
      -width / 2 - 4 * unit,
      -radius - 7 * unit,
      width + 8 * unit,
      14 * unit,
    );
    ctx.fillStyle = GRAPH_COLOR.orbitLabel;
    ctx.fillText(label, 0, -radius + 5 * unit);
  }
  ctx.restore();
}
