/** Narrowing helpers for request and response bodies (`unknown` JSON). */

export type JsonRecord = Readonly<Record<string, unknown>>;

export function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** The first key of `record` that holds a value other than null. */
export function pick(record: JsonRecord, keys: readonly string[]): unknown {
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null) return value;
  }
  return undefined;
}

export function asText(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return null;
}

export function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export const asArray = (value: unknown): readonly unknown[] =>
  Array.isArray(value) ? value : [];

export const textOf = (record: JsonRecord, keys: readonly string[]) =>
  asText(pick(record, keys));

export const numberOf = (record: JsonRecord, keys: readonly string[]) =>
  asNumber(pick(record, keys));
