import {
  REJECTION,
  type RejectionCode,
  type SourceDetail,
} from '@/domains/workspace';
import { percent } from '@/shared/lib/format';

import {
  humanize,
  numberAt,
  numberEntries,
  objectAt,
  signed,
  textAt,
  type Fact,
} from './record';

function isRejection(value: string): value is RejectionCode {
  return value in REJECTION;
}

/** A rejection code as words; unknown codes are humanized. */
export function rejectionLabel(code: string | null): string | null {
  if (!code || code === 'NONE') return null;
  return isRejection(code) ? REJECTION[code] : humanize(code);
}

function fact(label: string, value: string | null, mono = false): Fact | null {
  return value === null ? null : { label, value, mono };
}

/** Score, z, and votes from the source row; T is the vote threshold. */
function scoreFacts(
  source: SourceDetail['source'],
  votesNeeded: number | null,
): (Fact | null)[] {
  const votes = source.screen_votes;
  return [
    fact('Screen score', source.screen_score?.toFixed(2) ?? null),
    fact('z score', source.screen_z === null ? null : signed(source.screen_z)),
    fact(
      'Votes',
      votes === null
        ? null
        : `${votes}${votesNeeded ? `, needs ${votesNeeded}` : ''}`,
    ),
  ];
}

/** The screening JSON: relevance, confidence, votes, exclusion, method. */
function screenFacts(screen: SourceDetail['screen']): (Fact | null)[] {
  const relevance = numberAt(screen, 'relevance');
  const confidence = numberAt(screen, 'confidence');
  return [
    fact('Relevance', relevance?.toFixed(2) ?? null),
    fact('Confidence', confidence === null ? null : percent(confidence)),
    ...numberEntries(objectAt(screen, 'votes')).map(([criterion, value]) =>
      fact(`${humanize(criterion)} vote`, percent(value)),
    ),
    fact('Excluded for', rejectionLabel(textAt(screen, 'exclusion'))),
    fact('Method', textAt(screen, 'method'), true),
  ];
}

export function screeningFacts(
  detail: SourceDetail,
  votesNeeded: number | null,
): Fact[] {
  return [
    ...scoreFacts(detail.source, votesNeeded),
    ...screenFacts(detail.screen),
  ].filter((item): item is Fact => item !== null);
}
