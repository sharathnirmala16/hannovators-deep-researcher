import {
  CATEGORY_STYLE,
  LEGEND,
  LINK_LEGEND,
  LINK_STYLE,
  type NodeShape,
} from '../model/graphStyle';

/** A 12 px copy of the canvas shape, so the key matches the drawing. */
function ShapeSwatch({ shape, color }: { shape: NodeShape; color: string }) {
  const hollow = shape === 'ring' || shape === 'dashed-ring';
  return (
    <svg aria-hidden viewBox="0 0 12 12" className="size-3 shrink-0">
      {shape === 'diamond' ? (
        <path d="M6 1 L11 6 L6 11 L1 6 Z" fill={color} />
      ) : (
        <circle
          cx="6"
          cy="6"
          r={hollow ? 4 : 5}
          fill={hollow ? '#ffffff' : color}
          stroke={hollow ? color : 'none'}
          strokeWidth={1.4}
          strokeDasharray={shape === 'dashed-ring' ? '1.6 1.4' : undefined}
        />
      )}
      {shape === 'stamp' ? (
        <circle
          cx="6"
          cy="6"
          r="2.4"
          fill="none"
          stroke="#ffffff"
          strokeWidth={1.2}
        />
      ) : null}
    </svg>
  );
}

/** Node shapes, then the three line styles. */
export function GraphLegend() {
  return (
    <div className="flex flex-col gap-1 text-xs text-muted-foreground">
      <ul aria-label="Node shapes" className="flex flex-wrap gap-x-4 gap-y-1">
        {LEGEND.map((category) => (
          <li key={category} className="inline-flex items-center gap-1.5">
            <ShapeSwatch
              shape={CATEGORY_STYLE[category].shape}
              color={CATEGORY_STYLE[category].color}
            />
            {CATEGORY_STYLE[category].label}
          </li>
        ))}
      </ul>
      <ul aria-label="Line styles" className="flex flex-wrap gap-x-4 gap-y-1">
        {LINK_LEGEND.map((kind) => (
          <li key={kind} className="inline-flex items-center gap-1.5">
            <svg aria-hidden viewBox="0 0 16 4" className="h-1 w-4 shrink-0">
              <line
                x1="0"
                y1="2"
                x2="16"
                y2="2"
                stroke={LINK_STYLE[kind].color}
                strokeWidth={1.5}
                strokeDasharray={LINK_STYLE[kind].dash?.join(' ')}
              />
            </svg>
            {LINK_STYLE[kind].label}
          </li>
        ))}
      </ul>
    </div>
  );
}
