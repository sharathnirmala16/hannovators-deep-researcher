import { CATEGORY_STYLE, LEGEND } from '../model/graphStyle';

/** Node colors, then the two line styles. */
export function GraphLegend() {
  return (
    <div className="flex flex-col gap-1 text-xs text-muted-foreground">
      <ul aria-label="Node colors" className="flex flex-wrap gap-x-4 gap-y-1">
        {LEGEND.map((category) => (
          <li key={category} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className="size-2.5 rounded-full"
              // Cytoscape colors are literal hex; the swatch must match them.
              style={{ backgroundColor: CATEGORY_STYLE[category].color }}
            />
            {CATEGORY_STYLE[category].label}
          </li>
        ))}
      </ul>
      <ul aria-label="Line styles" className="flex flex-wrap gap-x-4 gap-y-1">
        <li className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="w-4 border-t border-solid border-shade-3"
          />
          Cites
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="w-4 border-t border-dashed border-shade-4"
          />
          Seed match
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="w-4 border-t border-dotted border-shade-3"
          />
          Related article
        </li>
      </ul>
    </div>
  );
}
