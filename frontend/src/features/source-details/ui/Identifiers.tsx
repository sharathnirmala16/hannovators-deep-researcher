import type { SourceDetail } from '@/domains/workspace';

import { textAt } from '../model/record';

const ORIGIN_ID: Record<SourceDetail['source']['origin'], string | null> = {
  PUBMED: 'PMID',
  EUROPEPMC: 'Europe PMC',
  WEB: null,
  SEED: null,
};

/** Identifiers in monospace: DOI, PMID, PMCID, and the origin's own ID. */
export function Identifiers({ detail }: { detail: SourceDetail }) {
  const { source, extra } = detail;
  const doi = textAt(extra, 'doi');
  const pmid = textAt(extra, 'pmid');
  const pmcid = textAt(extra, 'pmcid');
  const origin = ORIGIN_ID[source.origin];
  const ids = [
    doi ? ['DOI', doi] : null,
    pmid ? ['PMID', pmid] : null,
    pmcid ? ['PMCID', pmcid] : null,
    origin && source.external_id !== pmid ? [origin, source.external_id] : null,
  ].filter((id): id is [string, string] => id !== null);
  if (ids.length === 0 && !source.url) return null;
  return (
    <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
      {ids.map(([label, value]) => (
        <span key={label}>
          {label} <span className="font-mono text-foreground">{value}</span>
        </span>
      ))}
      {source.url ? (
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="max-w-full truncate font-mono text-link underline-offset-[3px] hover:underline"
          title={source.url}
        >
          {source.url}
        </a>
      ) : null}
    </p>
  );
}
