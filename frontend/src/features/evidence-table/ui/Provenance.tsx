import type { Synthesis } from '@/domains/workspace';
import { absoluteTime } from '@/shared/lib/format';

import { humanize } from './findings';

/** How the synthesis was made: models, canary, and time. Quiet by design. */
export function Provenance({
  provenance,
}: {
  provenance: Synthesis['provenance'];
}) {
  const models = Object.entries(provenance.models);
  return (
    <footer className="flex flex-col gap-2 pt-2 text-xs text-muted-foreground">
      <h3 className="font-medium">Provenance</h3>
      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1">
        {models.map(([role, model]) => (
          <div key={role} className="contents">
            <dt>{humanize(role.toLowerCase())} model</dt>
            <dd className="truncate font-mono" title={model}>
              {model}
            </dd>
          </div>
        ))}
        <dt>Canary</dt>
        <dd className="truncate font-mono">{provenance.canary}</dd>
        <dt>Generated</dt>
        <dd className="tabular-nums">
          <time dateTime={provenance.generated_at}>
            {absoluteTime(provenance.generated_at)}
          </time>
        </dd>
      </dl>
    </footer>
  );
}
