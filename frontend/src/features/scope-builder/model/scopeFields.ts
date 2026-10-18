import type {
  Decomposition,
  PicotsDecomposition,
  ScopeDecomposition,
} from '@/domains/workspace';

export type ScopeField<D> =
  | {
      kind: 'list';
      id: string;
      label: string;
      get: (value: D) => readonly string[];
      set: (value: D, next: string[]) => D;
    }
  | {
      kind: 'text';
      id: string;
      label: string;
      get: (value: D) => string;
      set: (value: D, next: string) => D;
    };

const orNull = (text: string) => (text.trim() ? text : null);

export const PICOTS_FIELDS: readonly ScopeField<PicotsDecomposition>[] = [
  {
    kind: 'text',
    id: 'population',
    label: 'Population',
    get: (d) => d.population,
    set: (d, population) => ({ ...d, population }),
  },
  {
    kind: 'list',
    id: 'interventions',
    label: 'Interventions',
    get: (d) => d.interventions,
    set: (d, interventions) => ({ ...d, interventions }),
  },
  {
    kind: 'list',
    id: 'comparisons',
    label: 'Comparisons',
    get: (d) => d.comparisons,
    set: (d, comparisons) => ({ ...d, comparisons }),
  },
  {
    kind: 'list',
    id: 'outcomes',
    label: 'Outcomes',
    get: (d) => d.outcomes,
    set: (d, outcomes) => ({ ...d, outcomes }),
  },
  {
    kind: 'text',
    id: 'timing',
    label: 'Timing',
    get: (d) => d.timing ?? '',
    set: (d, timing) => ({ ...d, timing: orNull(timing) }),
  },
  {
    kind: 'list',
    id: 'study_designs',
    label: 'Study designs',
    get: (d) => d.study_designs,
    set: (d, study_designs) => ({ ...d, study_designs }),
  },
];

export const SCOPE_FIELDS: readonly ScopeField<ScopeDecomposition>[] = [
  {
    kind: 'list',
    id: 'entities',
    label: 'Entities',
    get: (d) => d.entities,
    set: (d, entities) => ({ ...d, entities }),
  },
  {
    kind: 'list',
    id: 'claims',
    label: 'Claims',
    get: (d) => d.claims,
    set: (d, claims) => ({ ...d, claims }),
  },
  {
    kind: 'list',
    id: 'metrics',
    label: 'Metrics',
    get: (d) => d.metrics,
    set: (d, metrics) => ({ ...d, metrics }),
  },
  {
    kind: 'text',
    id: 'time_horizon',
    label: 'Time horizon',
    get: (d) => d.time_horizon ?? '',
    set: (d, horizon) => ({ ...d, time_horizon: orNull(horizon) }),
  },
  {
    kind: 'list',
    id: 'counter_hypotheses',
    label: 'Counter-hypotheses',
    get: (d) => d.counter_hypotheses,
    set: (d, counter_hypotheses) => ({ ...d, counter_hypotheses }),
  },
];

/** Adds a trimmed, non-duplicate entry. */
export function withEntry(list: readonly string[], entry: string): string[] {
  const text = entry.trim();
  if (!text || list.includes(text)) return [...list];
  return [...list, text];
}

export function withoutEntry(list: readonly string[], index: number): string[] {
  return list.filter((_, at) => at !== index);
}

export const SCOPE_TITLE: Record<Decomposition['mode'], string> = {
  MEDICAL: 'PICOTS',
  GENERAL: 'Research scope',
};
