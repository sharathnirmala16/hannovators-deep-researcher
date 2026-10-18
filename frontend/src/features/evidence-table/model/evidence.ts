import type {
  ClaimVerdict,
  ClaimView,
  GradeCertainty,
  SourceView,
  Synthesis,
} from '@/domains/workspace';

type GradeAssessment = Synthesis['pairwise_summaries'][number]['grade'];

export const GRADE_DOMAINS = [
  ['risk_of_bias', 'Risk of bias'],
  ['inconsistency', 'Inconsistency'],
  ['indirectness', 'Indirectness'],
  ['imprecision', 'Imprecision'],
  ['publication_bias', 'Publication bias'],
] as const satisfies readonly (readonly [keyof GradeAssessment, string])[];

export const CERTAINTY_LEVEL: Record<GradeCertainty, number> = {
  HIGH: 4,
  MODERATE: 3,
  LOW: 2,
  VERY_LOW: 1,
};

export const CERTAINTY_LABEL: Record<GradeCertainty, string> = {
  HIGH: 'High',
  MODERATE: 'Moderate',
  LOW: 'Low',
  VERY_LOW: 'Very low',
};

export interface DowngradeReason {
  domain: string;
  text: string;
}

const DOWNGRADE = /^(serious|very serious|suspected|strongly suspected)\b/i;

/** GRADE domains whose judgement downgrades the certainty. */
export function downgradeReasons(grade: GradeAssessment): DowngradeReason[] {
  return GRADE_DOMAINS.filter(([key]) => DOWNGRADE.test(grade[key].trim())).map(
    ([key, domain]) => ({ domain, text: grade[key] }),
  );
}

/** Short study label: first author surname and year, else the title. */
export function studyLabel(source: SourceView): string {
  const author = source.authors[0]?.split(' ')[0];
  if (author && source.year) return `${author} ${source.year}`;
  return source.title;
}

export function indexById<T extends { id: string }>(
  items: readonly T[],
): Map<string, T> {
  return new Map(items.map((item) => [item.id, item]));
}

export interface StudyClaims {
  intervention: ClaimView | undefined;
  comparison: ClaimView | undefined;
  others: ClaimView[];
}

/** Splits a study's claims into the two event arms and the rest. */
export function studyClaims(
  claims: readonly ClaimView[],
  sourceId: string,
): StudyClaims {
  const own = claims.filter(
    (claim) => claim.source_id === sourceId && claim.kind !== 'RECOMMENDATION',
  );
  const arm = (value: 'INTERVENTION' | 'COMPARISON') =>
    own.find((claim) => claim.kind === 'METRIC' && claim.arm === value);
  const intervention = arm('INTERVENTION');
  const comparison = arm('COMPARISON');
  return {
    intervention,
    comparison,
    others: own.filter(
      (claim) => claim !== intervention && claim !== comparison,
    ),
  };
}

const OPPOSED: Partial<Record<ClaimVerdict, readonly ClaimVerdict[]>> = {
  SUPPORTED: ['CONTRADICTED', 'MIXED'],
  CONTRADICTED: ['SUPPORTED', 'MIXED'],
  MIXED: ['SUPPORTED', 'CONTRADICTED'],
};

/**
 * Claims on the same outcome, from another source, with an opposed verdict.
 * Unverified claims and claims without an outcome have no contradictions.
 */
export function contradictions(
  claim: ClaimView,
  claims: readonly ClaimView[],
): ClaimView[] {
  const opposed = OPPOSED[claim.verdict];
  if (!opposed || claim.outcome === null) return [];
  return claims.filter(
    (other) =>
      other.id !== claim.id &&
      other.kind !== 'RECOMMENDATION' &&
      other.outcome === claim.outcome &&
      other.source_id !== claim.source_id &&
      opposed.includes(other.verdict),
  );
}

/** Claims grouped by outcome, in first-seen order. */
export function groupByOutcome(
  claims: readonly ClaimView[],
): [string, ClaimView[]][] {
  const groups = new Map<string, ClaimView[]>();
  for (const claim of claims) {
    if (claim.kind === 'RECOMMENDATION') continue;
    const key = claim.outcome ?? 'Other claims';
    const group = groups.get(key) ?? [];
    group.push(claim);
    groups.set(key, group);
  }
  return [...groups];
}
