import type { StageActivity, StageState } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { formatDuration, plural } from '@/shared/lib/format';

import { StageMarker } from './StageMarker';

const LABEL: Record<StageState, string> = {
  done: 'text-foreground',
  active: 'font-semibold text-foreground',
  review: 'font-semibold text-foreground',
  failed: 'font-semibold text-tone-negative',
  pending: 'text-muted-foreground',
};

const STATE_TEXT: Record<StageState, string> = {
  done: 'done',
  active: 'running',
  review: 'waiting for review',
  failed: 'failed',
  pending: 'not started',
};

function duration(activity: StageActivity | undefined): string {
  if (!activity?.startedAt || !activity.endedAt) return '';
  const ms =
    new Date(activity.endedAt).getTime() -
    new Date(activity.startedAt).getTime();
  return formatDuration(ms);
}

function note(state: StageState, activity: StageActivity | undefined) {
  if (state === 'review') return 'Waiting for your review';
  if (state === 'active' || state === 'failed') return activity?.message ?? '';
  return '';
}

interface StageRowProps {
  label: string;
  state: StageState;
  activity: StageActivity | undefined;
  last: boolean;
}

/** One stage: marker on the line, name, warnings, duration, live message. */
export function StageRow({ label, state, activity, last }: StageRowProps) {
  const message = note(state, activity);
  const warnings = activity?.warnings ?? 0;
  return (
    <li className="relative grid grid-cols-[1rem_minmax(0,1fr)_auto] items-start gap-x-2 py-1">
      {last ? null : (
        <span
          aria-hidden
          className={cn(
            'absolute top-[22px] -bottom-1.5 left-[7.5px] w-px',
            state === 'done' ? 'bg-shade-3' : 'bg-rule',
          )}
        />
      )}
      <StageMarker state={state} />
      <div className="flex min-w-0 flex-col">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className={cn('truncate text-sm', LABEL[state])} title={label}>
            {label}
          </span>
          <span className="sr-only">{STATE_TEXT[state]}</span>
          {warnings > 0 ? (
            <span className="shrink-0 text-xs text-tone-caution tabular-nums">
              {plural(warnings, 'warning')}
            </span>
          ) : null}
        </div>
        {message ? (
          <p
            className={cn(
              'truncate text-xs',
              state === 'review'
                ? 'text-tone-caution'
                : 'text-muted-foreground',
            )}
            title={message}
          >
            {message}
          </p>
        ) : null}
      </div>
      <span className="pt-0.5 text-xs text-muted-foreground tabular-nums">
        {duration(activity)}
      </span>
    </li>
  );
}
