import type { TrajectoryStatus, VerdictOutcome } from '@/domains/workspace';

/** Semantic status colors (PLAN.md section 10.2); everything else is neutral. */
export const STATUS_DOT: Record<TrajectoryStatus, string> = {
  OK: 'bg-emerald-500',
  ERROR: 'bg-rose-500',
  RUNNING: 'bg-sky-500 motion-safe:animate-pulse',
  SKIPPED: 'bg-muted-foreground/40',
};

export const STATUS_TEXT: Record<TrajectoryStatus, string> = {
  OK: 'text-muted-foreground',
  ERROR: 'text-rose-600 dark:text-rose-400',
  RUNNING: 'text-sky-600 dark:text-sky-400',
  SKIPPED: 'text-muted-foreground',
};

export const BAR_COLOR: Record<TrajectoryStatus, string> = {
  OK: 'bg-foreground/35',
  ERROR: 'bg-rose-500',
  RUNNING: 'bg-sky-500',
  SKIPPED: 'bg-muted-foreground/30',
};

export const OUTCOME_TONE: Record<VerdictOutcome, string> = {
  KEPT: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  REMOVED: 'bg-rose-500/10 text-rose-700 dark:text-rose-400',
  FLAGGED: 'bg-amber-500/15 text-amber-800 dark:text-amber-300',
};

export const OUTCOME_TEXT: Record<VerdictOutcome, string> = {
  KEPT: 'text-emerald-700 dark:text-emerald-400',
  REMOVED: 'text-rose-700 dark:text-rose-400',
  FLAGGED: 'text-amber-700 dark:text-amber-300',
};

/** Native scrollbars in one thin style that never toggles on hover. */
export const SCROLL_Y =
  'overflow-y-auto [scrollbar-gutter:stable] [scrollbar-width:thin] [scrollbar-color:var(--color-border)_transparent]';

export const FOCUS_RING =
  'outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background';
