import type { SourceView } from '@/domains/workspace';

import { rejectionCounts } from '../model/funnel';

/** Why sources left the flow, most frequent reason first. */
export function RemovalReasons({
  sources,
}: {
  sources: readonly SourceView[];
}) {
  const reasons = rejectionCounts(sources);
  if (reasons.length === 0) return null;
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <h4 className="text-xs font-medium text-muted-foreground">
        Why sources were removed
      </h4>
      <ul className="flex min-w-0 flex-col">
        {reasons.map((reason) => (
          <li
            key={reason.code}
            className="flex min-w-0 items-baseline gap-2 py-0.5 text-sm"
          >
            <span className="truncate text-foreground" title={reason.label}>
              {reason.label}
            </span>
            <span className="ml-auto shrink-0 text-tone-negative tabular-nums">
              {reason.count}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
