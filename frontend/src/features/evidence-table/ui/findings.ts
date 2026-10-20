import type { ClaimView } from '@/domains/workspace';

/**
 * View shaping for the evidence profile: which of a study's claims belong to
 * an outcome row. Claim outcomes are free text from the appraisal model, so
 * the match is by shared content words, not by equality.
 */

const STOP = new Set([
  'with',
  'from',
  'during',
  'after',
  'before',
  'within',
  'incidence',
  'rate',
  'rates',
  'total',
  'overall',
  'patients',
  'adult',
  'adults',
  'that',
  'this',
  'than',
  'into',
  'over',
  'events',
  'event',
  'outcome',
  'outcomes',
  'stay',
  'days',
  'length',
  'risk',
  'number',
]);

function contentWords(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((word) => word.length >= 4 && !STOP.has(word)),
  );
}

/** Two outcome names share at least half of the shorter one's content words. */
export function sameOutcome(a: string, b: string): boolean {
  const left = contentWords(a);
  const right = contentWords(b);
  const smaller = Math.min(left.size, right.size);
  if (smaller === 0) return a.trim().toLowerCase() === b.trim().toLowerCase();
  const shared = [...left].filter((word) => right.has(word)).length;
  return shared / smaller >= 0.5;
}

/** Arm counts such as "386/2373"; long sentences are findings, not counts. */
const SHORT_VALUE = 28;

export interface OutcomeFindings {
  /** Intervention and comparison event counts, when both are reported. */
  events: readonly [ClaimView, ClaimView] | null;
  /** The study's other results for this outcome. */
  findings: ClaimView[];
  /** Results for other outcomes. */
  others: ClaimView[];
}

function armValue(
  claims: readonly ClaimView[],
  arm: 'INTERVENTION' | 'COMPARISON',
): ClaimView | undefined {
  return claims.find(
    (claim) =>
      claim.kind === 'METRIC' &&
      claim.arm === arm &&
      claim.text.length <= SHORT_VALUE,
  );
}

/** One study's claims, split into this outcome's results and the rest. */
export function outcomeFindings(
  claims: readonly ClaimView[],
  sourceId: string,
  outcome: string,
): OutcomeFindings {
  const own = claims.filter(
    (claim) => claim.source_id === sourceId && claim.kind !== 'RECOMMENDATION',
  );
  const matching = own.filter(
    (claim) => claim.outcome !== null && sameOutcome(claim.outcome, outcome),
  );
  const intervention = armValue(matching, 'INTERVENTION');
  const comparison = armValue(matching, 'COMPARISON');
  const events =
    intervention && comparison ? ([intervention, comparison] as const) : null;
  return {
    events,
    findings: matching.filter(
      (claim) => claim !== intervention && claim !== comparison,
    ),
    others: own.filter((claim) => !matching.includes(claim)),
  };
}

/** "overall_delirium_incidence" reads as "Overall delirium incidence". */
export function humanize(text: string): string {
  const spaced = text.replace(/_/g, ' ').trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
