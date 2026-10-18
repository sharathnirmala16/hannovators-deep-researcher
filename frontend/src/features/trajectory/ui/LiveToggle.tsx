import { cn } from '@/shared/lib/cn';

import type { LiveStatus } from '../model/useTrajectory';
import { FOCUS_RING } from './statusStyles';

const LABEL: Record<LiveStatus, string> = {
  off: 'Paused',
  connecting: 'Connecting',
  live: 'Live',
  interrupted: 'Stream interrupted',
};

const DOT: Record<LiveStatus, string> = {
  off: 'bg-muted-foreground/50',
  connecting: 'bg-sky-500/60',
  live: 'bg-sky-500 motion-safe:animate-pulse',
  interrupted: 'bg-amber-500',
};

interface LiveToggleProps {
  live: boolean;
  status: LiveStatus;
  onChange: (live: boolean) => void;
}

/** Pauses or resumes the live step stream. */
export function LiveToggle({ live, status, onChange }: LiveToggleProps) {
  return (
    <button
      type="button"
      aria-pressed={live}
      title={live ? 'Pause live updates' : 'Resume live updates'}
      onClick={() => onChange(!live)}
      className={cn(
        'inline-flex h-7 items-center gap-1.5 rounded-md border border-input px-2 text-xs transition-colors hover:bg-muted',
        FOCUS_RING,
      )}
    >
      <span aria-hidden className={cn('size-2 rounded-full', DOT[status])} />
      {LABEL[status]}
    </button>
  );
}
