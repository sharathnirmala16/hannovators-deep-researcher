export type SeedKind = 'pmid' | 'doi' | 'url';

export interface SeedReference {
  kind: SeedKind;
  value: string;
}

const DOI_URL = /^(?:https?:\/\/)?(?:dx\.)?doi\.org\/(10\.\d{4,9}\/\S+)$/i;
const DOI = /^(?:doi:\s*)?(10\.\d{4,9}\/\S+)$/i;
const PMID = /^(?:pmid:\s*)?(\d{1,9})$/i;
const URL_LIKE = /^https?:\/\/\S+\.\S+/i;

/** Reads a PMID, DOI (bare, `doi:`, or doi.org link), or URL. */
export function parseSeedReference(input: string): SeedReference | null {
  const text = input.trim();
  const doi = DOI_URL.exec(text)?.[1] ?? DOI.exec(text)?.[1];
  if (doi) return { kind: 'doi', value: doi };
  const pmid = PMID.exec(text)?.[1];
  if (pmid) return { kind: 'pmid', value: pmid };
  if (URL_LIKE.test(text)) return { kind: 'url', value: text };
  return null;
}

export const SEED_KIND_LABEL: Record<SeedKind, string> = {
  pmid: 'PMID',
  doi: 'DOI',
  url: 'URL',
};
