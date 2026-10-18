import {
  STAGES,
  STAGE_LABEL,
  stageActivity,
  stageStates,
  useWorkspace,
  type EventStreamStatus,
  type StageActivity,
  type StageState,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { formatDuration, plural } from '@/shared/lib/format';
import { SectionHeader } from '@/shared/ui/section-header';

const DOT: Record<StageState, string> = {
  done: 'bg-shade-6',
  active: 'bg-tone-info ring-4 ring-border animate-pulse',
  review: 'bg-tone-caution ring-4 ring-border',
  failed: 'bg-tone-negative',
  pending: 'bg-background ring-1 ring-shade-4',
};

const STREAM_TEXT: Record<EventStreamStatus, string> = {
  idle: '',
  open: 'Live',
  ended: 'Ended',
  error: 'Reconnecting',
};

function duration(activity: StageActivity | undefined): string {
  if (!activity?.startedAt || !activity.endedAt) return '';
  const ms =
    new Date(activity.endedAt).getTime() -
    new Date(activity.startedAt).getTime();
  return formatDuration(ms);
}

function StageRow({
  label,
  state,
  activity,
}: {
  label: string;
  state: StageState;
  activity: StageActivity | undefined;
}) {
  const showMessage = state === 'active' || state === 'failed';
  return (
    <li className="relative flex gap-2 pb-2 last:pb-0">
      <span
        aria-hidden
        className={cn('mt-1.5 size-2 shrink-0 rounded-full', DOT[state])}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-baseline gap-2">
          <span
            className={cn(
              'text-sm',
              state === 'pending' ? 'text-muted-foreground' : 'text-foreground',
            )}
          >
            {label}
          </span>
          {activity && activity.warnings > 0 ? (
            <span className="text-xs text-tone-caution">
              {plural(activity.warnings, 'warning')}
            </span>
          ) : null}
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">
            {duration(activity)}
          </span>
        </div>
        {showMessage && activity?.message ? (
          <p
            className="truncate text-xs text-muted-foreground"
            title={activity.message}
          >
            {activity.message}
          </p>
        ) : null}
      </div>
    </li>
  );
}

/** Compact run timeline: one row per stage, from the live trace events. */
export function RunTimeline() {
  const { load, events, eventStatus } = useWorkspace();
  if (load.status !== 'ready') return null;
  const { workspace } = load.state;
  const states = stageStates(workspace, events);
  const activity = new Map(
    stageActivity(events).map((item) => [item.stage, item]),
  );
  return (
    <section
      aria-labelledby="run-timeline-title"
      className="flex flex-col gap-2"
    >
      <SectionHeader
        id="run-timeline-title"
        title="Run"
        meta={
          events.length > 0 ? (
            <span>
              {STREAM_TEXT[eventStatus]}, {plural(events.length, 'event')}
            </span>
          ) : null
        }
      />
      {workspace.error ? (
        <p className="rounded-sm bg-shade-2 px-2 py-1 text-xs text-tone-negative">
          {workspace.error}
        </p>
      ) : null}
      <ol aria-label="Stages" className="flex flex-col">
        {STAGES.map((stage) => (
          <StageRow
            key={stage}
            label={STAGE_LABEL[stage]}
            state={states[stage]}
            activity={activity.get(stage)}
          />
        ))}
      </ol>
    </section>
  );
}
