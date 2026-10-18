import type { TrajectoryStepSummary } from '@/domains/workspace';

type Step = TrajectoryStepSummary;

export interface TimeRange {
  start: number;
  end: number;
}

const startOf = (step: Step) => Date.parse(step.started_at);

/** End time in ms, or null while the step is still open. */
function endOf(step: Step): number | null {
  if (step.ended_at) return Date.parse(step.ended_at);
  if (step.duration_ms !== null) return startOf(step) + step.duration_ms;
  return null;
}

/** First start and last known end across `steps`. */
export function timeRange(steps: readonly Step[]): TimeRange | null {
  let start = Infinity;
  let end = -Infinity;
  for (const step of steps) {
    const begin = startOf(step);
    start = Math.min(start, begin);
    end = Math.max(end, endOf(step) ?? begin);
  }
  return Number.isFinite(start) ? { start, end } : null;
}

export interface Bar {
  /** Percent of the range. */
  left: number;
  width: number;
  open: boolean;
}

/** Waterfall geometry; an open step runs to the end of the range. */
export function barFor(step: Step, range: TimeRange): Bar {
  const span = Math.max(range.end - range.start, 1);
  const begin = startOf(step);
  const finish = endOf(step);
  const left = ((begin - range.start) / span) * 100;
  const width = (((finish ?? range.end) - begin) / span) * 100;
  return {
    left: clamp(left, 0, 100),
    width: clamp(width, 0, 100 - clamp(left, 0, 100)),
    open: finish === null,
  };
}

const clamp = (value: number, low: number, high: number) =>
  Math.min(Math.max(value, low), high);

export function offsetMs(step: Step, origin: number): number {
  return startOf(step) - origin;
}

export function formatDuration(ms: number | null): string {
  if (ms === null) return '';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes} min ${String(seconds).padStart(2, '0')} s`;
}

/** Offset since the first step, for example `12.40 s` or `3:05.2`. */
export function formatOffset(ms: number): string {
  const safe = Math.max(ms, 0);
  if (safe < 60_000) return `${(safe / 1000).toFixed(2)} s`;
  const minutes = Math.floor(safe / 60_000);
  const seconds = ((safe % 60_000) / 1000).toFixed(1).padStart(4, '0');
  return `${minutes}:${seconds}`;
}

export function formatClock(iso: string): string {
  const date = new Date(iso);
  const time = date.toLocaleTimeString(undefined, { hour12: false });
  return `${time}.${String(date.getMilliseconds()).padStart(3, '0')}`;
}

export function formatPercent(value: number | null): string {
  return value === null ? '' : `${Math.round(value * 100)}%`;
}

export const formatCount = (value: number) => value.toLocaleString();
