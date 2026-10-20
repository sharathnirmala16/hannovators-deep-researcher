import type { SourceDetail } from '@/domains/workspace';

import { criteriaOf, humanize, textAt, type Fact } from './record';
import { rejectionLabel } from './screeningFacts';

function mScore(detail: SourceDetail, needed: number | null): Fact | null {
  const m = detail.source.m_score;
  if (m === null) return null;
  const of = criteriaOf(detail.appraisal).length;
  const parts = [of > 0 ? `${m} of ${of} criteria met` : String(m)];
  if (needed !== null) parts.push(`needs ${needed}`);
  return { label: 'M-score', value: parts.join(', ') };
}

/** The appraisal explanation, unless the decision text already says it. */
function explanation(detail: SourceDetail): Fact | null {
  const text = textAt(detail.appraisal, 'explanation');
  const decision = detail.source.decision_explanation ?? '';
  if (!text || decision.includes(text)) return null;
  return { label: 'Explanation', value: text };
}

/** M-score, directness, basis, rejection, explanation. */
export function appraisalFacts(
  detail: SourceDetail,
  needed: number | null,
): Fact[] {
  const { source, appraisal } = detail;
  const basis = textAt(appraisal, 'basis');
  const rejection = rejectionLabel(source.rejection_code);
  const facts: (Fact | null)[] = [
    mScore(detail, needed),
    source.directness
      ? { label: 'Directness', value: humanize(source.directness) }
      : null,
    basis ? { label: 'Appraised from', value: humanize(basis) } : null,
    rejection && source.rejection_code
      ? { label: 'Rejection', value: `${rejection} (${source.rejection_code})` }
      : null,
    explanation(detail),
  ];
  return facts.filter((fact): fact is Fact => fact !== null);
}
