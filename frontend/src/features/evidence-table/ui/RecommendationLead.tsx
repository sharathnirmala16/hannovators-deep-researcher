import type {
  RecommendationDirection,
  RecommendationStrength,
  Synthesis,
} from '@/domains/workspace';
import { plainMath } from '@/shared/lib/plainMath';
import { Tag, type Tone } from '@/shared/ui/tag';

import type { CitationIndex } from './citations';
import { CitedText } from './CitedText';

const DIRECTION: Record<RecommendationDirection, { tag: string; tone: Tone }> =
  {
    FOR: { tag: 'For', tone: 'positive' },
    AGAINST: { tag: 'Against', tone: 'negative' },
    NONE: { tag: 'No direction', tone: 'neutral' },
  };

const STRENGTH: Record<RecommendationStrength, string> = {
  STRONG: 'Strong',
  CONDITIONAL: 'Conditional',
};

/** "Conditional recommendation against early mobilization". */
function statementOf(
  recommendation: Synthesis['recommendation'],
  subject: string | null,
): string {
  const strength = STRENGTH[recommendation.strength];
  if (!subject) {
    return recommendation.direction === 'NONE'
      ? 'No recommended direction'
      : `${strength} recommendation`;
  }
  const what = plainMath(subject);
  switch (recommendation.direction) {
    case 'FOR':
      return `${strength} recommendation for ${what}`;
    case 'AGAINST':
      return `${strength} recommendation against ${what}`;
    case 'NONE':
      return `No recommendation for or against ${what}`;
  }
}

interface RecommendationLeadProps {
  recommendation: Synthesis['recommendation'];
  /** What is recommended, when the synthesis compares one intervention. */
  subject: string | null;
  citations: CitationIndex;
}

/** The answer first: direction and strength, then the recommendation. */
export function RecommendationLead({
  recommendation,
  subject,
  citations,
}: RecommendationLeadProps) {
  const direction = DIRECTION[recommendation.direction];
  return (
    <section
      aria-labelledby="synthesis-recommendation"
      className="flex flex-col gap-3 rounded-md bg-desk px-4 py-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Tag tone={direction.tone}>{direction.tag}</Tag>
        <Tag>{STRENGTH[recommendation.strength]}</Tag>
        <h3
          id="synthesis-recommendation"
          className="min-w-0 text-sm font-semibold text-foreground"
        >
          {statementOf(recommendation, subject)}
        </h3>
      </div>
      <p className="reading max-w-[72ch] text-lg text-foreground">
        <CitedText text={recommendation.text} citations={citations} />
      </p>
    </section>
  );
}
