import {
  evidenceRank,
  studyLabel,
  type EvidenceStance,
  type SearchIntent,
  type SourceStatus,
  type SourceView,
} from '@/domains/workspace';

export type SortKey =
  'title' | 'level' | 'intent' | 'status' | 'stance' | 'score';

export interface Sort {
  key: SortKey;
  /** `asc` is the natural order: A to Z, strongest first, highest score. */
  direction: 'asc' | 'desc';
}

export type StatusFilter = 'all' | 'kept' | 'removed' | 'seeds';

const STATUS_ORDER: readonly SourceStatus[] = [
  'SEED',
  'APPRAISE_PROMOTED',
  'SCREEN_PROMOTED',
  'ACQUIRE_FAILED',
  'RAW',
  'APPRAISE_DISCOUNTED',
  'SCREEN_DISCOUNTED',
];

const STANCE_ORDER: readonly EvidenceStance[] = [
  'SUPPORTS',
  'OPPOSES',
  'NULL_RESULT',
  'MIXED',
  'ALTERNATIVE',
  'UNCLEAR',
];

const INTENT_ORDER: readonly SearchIntent[] = [
  'CORE',
  'NEGATIVE',
  'ALTERNATIVE',
  'SAFETY',
  'SEED_CITATION',
  'DEEP_RESEARCH',
];

/** Position in `order`; missing values sort last. */
function position<T>(order: readonly T[], value: T | null): number {
  const at = value === null ? -1 : order.indexOf(value);
  return at === -1 ? order.length : at;
}

const COMPARE: Record<SortKey, (a: SourceView, b: SourceView) => number> = {
  title: (a, b) => a.title.localeCompare(b.title),
  level: (a, b) => evidenceRank(a) - evidenceRank(b),
  intent: (a, b) =>
    position(INTENT_ORDER, a.search_intent) -
    position(INTENT_ORDER, b.search_intent),
  status: (a, b) =>
    position(STATUS_ORDER, a.status) - position(STATUS_ORDER, b.status),
  stance: (a, b) =>
    position(STANCE_ORDER, a.stance) - position(STANCE_ORDER, b.stance),
  score: (a, b) =>
    (b.screen_score ?? Number.NEGATIVE_INFINITY) -
    (a.screen_score ?? Number.NEGATIVE_INFINITY),
};

/** Sorted copy; ties fall back to the screen score, then the study label. */
export function sortSources(
  sources: readonly SourceView[],
  sort: Sort,
): SourceView[] {
  const sign = sort.direction === 'asc' ? 1 : -1;
  return [...sources].sort(
    (a, b) =>
      sign * COMPARE[sort.key](a, b) ||
      COMPARE.score(a, b) ||
      studyLabel(a).localeCompare(studyLabel(b)),
  );
}

const KEPT: ReadonlySet<SourceStatus> = new Set([
  'SCREEN_PROMOTED',
  'APPRAISE_PROMOTED',
]);
const REMOVED: ReadonlySet<SourceStatus> = new Set([
  'SCREEN_DISCOUNTED',
  'APPRAISE_DISCOUNTED',
]);

export function matchesFilter(
  source: SourceView,
  filter: StatusFilter,
): boolean {
  switch (filter) {
    case 'all':
      return true;
    case 'kept':
      return KEPT.has(source.status);
    case 'removed':
      return REMOVED.has(source.status);
    case 'seeds':
      return source.status === 'SEED';
  }
}
