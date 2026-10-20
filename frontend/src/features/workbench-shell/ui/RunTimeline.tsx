import {
  STAGES,
  stageStates,
  useWorkspace,
  type EventStreamStatus,
} from '@/domains/workspace';
import { SectionHeader } from '@/shared/ui/section-header';
import { SkeletonBlock } from '@/shared/ui/states';
import { ToneDot, type Tone } from '@/shared/ui/tag';

import { RunStages } from './RunStages';

const STREAM: Record<EventStreamStatus, { text: string; tone: Tone } | null> = {
  idle: null,
  open: { text: 'Live', tone: 'info' },
  ended: { text: 'Ended', tone: 'neutral' },
  error: { text: 'Reconnecting', tone: 'caution' },
};

function StreamStatus({ status }: { status: EventStreamStatus }) {
  const stream = STREAM[status];
  if (!stream) return null;
  return (
    <span className="inline-flex items-center gap-1.5">
      <ToneDot tone={stream.tone} live={status === 'open'} />
      {stream.text}
    </span>
  );
}

/** Compact run timeline: the nine stages on one line, from the live trace events. */
export function RunTimeline() {
  const { load, events, eventStatus } = useWorkspace();
  if (load.status === 'error') return null;
  const workspace = load.status === 'ready' ? load.state.workspace : null;
  const started =
    workspace !== null && (workspace.status !== 'CREATED' || events.length > 0);
  const states = workspace ? stageStates(workspace, events) : null;
  const done = states
    ? STAGES.filter((stage) => states[stage] === 'done').length
    : 0;

  return (
    <section
      aria-labelledby="run-timeline-title"
      className="flex min-w-0 flex-col gap-2"
    >
      <SectionHeader
        id="run-timeline-title"
        title="Run"
        meta={
          started ? (
            <>
              <span>
                {done} of {STAGES.length} stages
              </span>
              <StreamStatus status={eventStatus} />
            </>
          ) : null
        }
      />
      {workspace ? (
        <RunStages workspace={workspace} events={events} started={started} />
      ) : (
        <SkeletonBlock lines={6} label="Loading the run" />
      )}
    </section>
  );
}
