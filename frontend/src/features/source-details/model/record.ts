import type { ReactNode } from 'react';

import type { SourceDetail } from '@/domains/workspace';

/**
 * Readers for the free-form JSON parts of a source detail (`screen`,
 * `appraisal`, `extra`). The backend fills them per stage, so every field is
 * optional and checked at runtime.
 */

type Json = SourceDetail['screen'][string];
export type JsonObject = { [key: string]: Json };

export function isObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function numberAt(record: JsonObject, key: string): number | null {
  const value = record[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function textAt(record: JsonObject, key: string): string | null {
  const value = record[key];
  return typeof value === 'string' && value.trim() ? value : null;
}

export function objectAt(record: JsonObject, key: string): JsonObject {
  const value = record[key];
  return isObject(value) ? value : {};
}

export interface Criterion {
  criterion: string;
  matched: boolean | null;
  rationale: string | null;
}

/** Appraisal criteria (PICO letters or scope items), when present. */
export function criteriaOf(appraisal: JsonObject): Criterion[] {
  const list = appraisal.criteria;
  if (!Array.isArray(list)) return [];
  return list.filter(isObject).map((item) => ({
    criterion: textAt(item, 'criterion') ?? 'Criterion',
    matched: typeof item.matched === 'boolean' ? item.matched : null,
    rationale: textAt(item, 'rationale'),
  }));
}

/** Numeric entries of an object, for example the screening votes. */
export function numberEntries(record: JsonObject): [string, number][] {
  return Object.entries(record).flatMap(([key, value]) =>
    typeof value === 'number' ? [[key, value] as [string, number]] : [],
  );
}

/** "abstract-only" or "selective_reporting" reads as a sentence-case phrase. */
export function humanize(text: string): string {
  const spaced = text.replace(/[_-]+/g, ' ').trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

/** "+2.81", "-0.40". */
export function signed(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`;
}

const PICO: Record<string, string> = {
  P: 'Population',
  I: 'Intervention',
  C: 'Comparison',
  O: 'Outcome',
  T: 'Timing',
  S: 'Study design',
};

export function criterionName(criterion: string): string {
  return PICO[criterion] ?? criterion;
}

/** One row of a definition list. */
export interface Fact {
  label: string;
  value: ReactNode;
  /** IDs, codes, and model names. */
  mono?: boolean;
}
