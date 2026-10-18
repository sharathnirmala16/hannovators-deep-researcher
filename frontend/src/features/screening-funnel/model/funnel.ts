import {
  REJECTION,
  isKeptSource,
  type Funnel,
  type RejectionCode,
  type SearchIntent,
  type SourceView,
} from '@/domains/workspace';

export interface FunnelStep {
  id: string;
  label: string;
  count: number;
  /** Records that left the flow at this step. */
  removed: { label: string; count: number } | null;
}

/** PRISMA-style flow: found, screened, full text, appraised. */
export function funnelSteps(funnel: Funnel): FunnelStep[] {
  const screened = funnel.screen_promoted + funnel.screen_discounted;
  return [
    {
      id: 'found',
      label: 'Records found',
      count: Math.max(funnel.raw, screened),
      removed: null,
    },
    {
      id: 'screened',
      label: 'Passed screening',
      count: funnel.screen_promoted,
      removed: { label: 'screened out', count: funnel.screen_discounted },
    },
    {
      id: 'full-text',
      label: 'Full text read',
      count: Math.max(0, funnel.screen_promoted - funnel.acquire_failed),
      removed: { label: 'no full text', count: funnel.acquire_failed },
    },
    {
      id: 'included',
      label: 'Included',
      count: funnel.appraise_promoted,
      removed: { label: 'excluded', count: funnel.appraise_discounted },
    },
  ];
}

/** The four intents every search runs; absent ones show as zero. */
const ALWAYS: readonly SearchIntent[] = [
  'CORE',
  'NEGATIVE',
  'ALTERNATIVE',
  'SAFETY',
];
const OPTIONAL: readonly SearchIntent[] = ['SEED_CITATION', 'DEEP_RESEARCH'];

export interface IntentCount {
  intent: SearchIntent;
  found: number;
  kept: number;
}

/** Sources found and kept per search intent; empty when none is recorded. */
export function intentCounts(sources: readonly SourceView[]): IntentCount[] {
  const tagged = sources.filter((source) => source.search_intent !== null);
  if (tagged.length === 0) return [];
  const count = (intent: SearchIntent): IntentCount => {
    const own = tagged.filter((source) => source.search_intent === intent);
    return {
      intent,
      found: own.length,
      kept: own.filter(isKeptSource).length,
    };
  };
  return [
    ...ALWAYS.map(count),
    ...OPTIONAL.map(count).filter((item) => item.found > 0),
  ];
}

export interface ReasonCount {
  code: RejectionCode;
  label: string;
  count: number;
}

/** Rejection reasons, most frequent first. */
export function rejectionCounts(sources: readonly SourceView[]): ReasonCount[] {
  const counts = new Map<RejectionCode, number>();
  for (const source of sources) {
    if (source.rejection_code) {
      counts.set(
        source.rejection_code,
        (counts.get(source.rejection_code) ?? 0) + 1,
      );
    }
  }
  return [...counts]
    .map(([code, count]) => ({ code, label: REJECTION[code], count }))
    .sort((a, b) => b.count - a.count);
}
