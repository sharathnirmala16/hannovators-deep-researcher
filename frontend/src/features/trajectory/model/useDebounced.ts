import { useEffect, useRef, useState } from 'react';

/** `value`, updated once it has been stable for `delayMs`. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return settled;
}

/**
 * Calls `effect` once `value` has been stable for `delayMs`, skipping the
 * first value. Used to audit settled UI actions, not every keystroke.
 */
export function useSettledEffect<T>(
  value: T,
  delayMs: number,
  effect: (value: T) => void,
): void {
  const initial = useRef(value);
  const latest = useRef(effect);
  useEffect(() => {
    latest.current = effect;
  });
  useEffect(() => {
    if (Object.is(value, initial.current)) return undefined;
    const timer = window.setTimeout(() => latest.current(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
}
