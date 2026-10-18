import type { TrajectoryStatus, VerdictOutcome } from '@/domains/workspace';

/** Semantic status colors (PLAN.md section 10.2); everything else is neutral. */
export const STATUS_DOT: Record<TrajectoryStatus, string> = {
  OK: 'bg-tone-positive',
  ERROR: 'bg-tone-negative',
  RUNNING: 'bg-tone-info motion-safe:animate-pulse',
  SKIPPED: 'bg-muted-foreground/40',
};

export const STATUS_TEXT: Record<TrajectoryStatus, string> = {
  OK: 'text-muted-foreground',
  ERROR: 'text-tone-negative',
  RUNNING: 'text-tone-info',
  SKIPPED: 'text-muted-foreground',
};

export const BAR_COLOR: Record<TrajectoryStatus, string> = {
  OK: 'bg-foreground/35',
  ERROR: 'bg-tone-negative',
  RUNNING: 'bg-tone-info',
  SKIPPED: 'bg-muted-foreground/30',
};

export const OUTCOME_TONE: Record<VerdictOutcome, string> = {
  KEPT: 'bg-tone-positive/10 text-tone-positive',
  REMOVED: 'bg-tone-negative/10 text-tone-negative',
  FLAGGED: 'bg-tone-caution/15 text-tone-caution',
};

export const OUTCOME_TEXT: Record<VerdictOutcome, string> = {
  KEPT: 'text-tone-positive',
  REMOVED: 'text-tone-negative',
  FLAGGED: 'text-tone-caution',
};

/** Native scrollbars in one thin style that never toggles on hover. */
export const SCROLL_Y =
  'overflow-y-auto [scrollbar-gutter:stable] [scrollbar-width:thin] [scrollbar-color:var(--color-border)_transparent]';

export const FOCUS_RING =
  'outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background';
