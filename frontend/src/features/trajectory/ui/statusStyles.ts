import type { TrajectoryStatus, VerdictOutcome } from '@/domains/workspace';

/** Semantic status colors (PLAN.md section 10.2); everything else is neutral. */
export const STATUS_DOT: Record<TrajectoryStatus, string> = {
  OK: 'bg-tone-positive',
  ERROR: 'bg-tone-negative',
  RUNNING: 'bg-tone-info motion-safe:animate-pulse',
  SKIPPED: 'bg-shade-4',
};

export const STATUS_TEXT: Record<TrajectoryStatus, string> = {
  OK: 'text-muted-foreground',
  ERROR: 'text-tone-negative',
  RUNNING: 'text-tone-info',
  SKIPPED: 'text-muted-foreground',
};

export const BAR_COLOR: Record<TrajectoryStatus, string> = {
  OK: 'bg-shade-4',
  ERROR: 'bg-tone-negative',
  RUNNING: 'bg-tone-info',
  SKIPPED: 'bg-shade-4',
};

export const OUTCOME_TONE: Record<VerdictOutcome, string> = {
  KEPT: 'bg-shade-2 text-tone-positive',
  REMOVED: 'bg-shade-2 text-tone-negative',
  FLAGGED: 'bg-shade-2 text-tone-caution',
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
