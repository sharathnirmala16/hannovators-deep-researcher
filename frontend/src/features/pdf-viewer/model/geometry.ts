/**
 * Highlight geometry. Rects come from PyMuPDF (`page.search_for`): PDF points
 * `[x0, y0, x1, y1]` with a top-left origin at the crop box corner, y down,
 * on the unrotated page. pdf.js renders the crop box (`page.view`), so on an
 * unrotated page the CSS box is simply the rect times the scale. Rotated
 * pages turn the rect with the page.
 */

export type PdfRect = readonly [number, number, number, number];

/** A rect on a 1-based page. */
export interface PageRect {
  page: number;
  rect: PdfRect;
}

/** Page size at scale 1 (unrotated crop box) plus the page rotation. */
export interface PageGeometry {
  page: number;
  /** Unrotated crop box width and height in PDF points. */
  viewWidth: number;
  viewHeight: number;
  /** 0, 90, 180, or 270. */
  rotation: number;
}

export interface CssBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Rendered page size in CSS pixels. */
export function pageCssSize(geometry: PageGeometry, scale: number) {
  const turned = geometry.rotation % 180 !== 0;
  const width = turned ? geometry.viewHeight : geometry.viewWidth;
  const height = turned ? geometry.viewWidth : geometry.viewHeight;
  return { width: width * scale, height: height * scale };
}

function rotatePoint(
  [x, y]: readonly [number, number],
  { viewWidth: w, viewHeight: h, rotation }: PageGeometry,
): [number, number] {
  switch (rotation) {
    case 90:
      return [h - y, x];
    case 180:
      return [w - x, h - y];
    case 270:
      return [y, w - x];
    default:
      return [x, y];
  }
}

/** Maps a top-left-origin PDF rect to a CSS box on the rendered page. */
export function toCssBox(
  rect: PdfRect,
  geometry: PageGeometry,
  scale: number,
): CssBox {
  const [ax, ay] = rotatePoint([rect[0], rect[1]], geometry);
  const [bx, by] = rotatePoint([rect[2], rect[3]], geometry);
  return {
    left: Math.min(ax, bx) * scale,
    top: Math.min(ay, by) * scale,
    width: Math.abs(bx - ax) * scale,
    height: Math.abs(by - ay) * scale,
  };
}
