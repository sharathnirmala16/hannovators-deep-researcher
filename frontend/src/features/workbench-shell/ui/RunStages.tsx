import {
  STAGES,
  STAGE_LABEL,
  stageActivity,
  stageStates,
  type TraceEvent,
  type WorkspaceState,
} from '@/domains/workspace';
import { EmptyState, ErrorState } from '@/shared/ui/states';

import { StageRow } from './StageRow';

interface RunStagesProps {
  workspace: WorkspaceState['workspace'];
  events: readonly TraceEvent[];
  started: boolean;
}

/** The run error, then the nine stages; an empty state before the run starts. */
export function RunStages({ workspace, events, started }: RunStagesProps) {
  if (!started) {
    return (
      <EmptyState title="The run has not started">
        Use Start run in the header. The nine stages appear here as they
        progress.
      </EmptyState>
    );
  }
  const states = stageStates(workspace, events);
  const activity = new Map(
    stageActivity(events).map((item) => [item.stage, item]),
  );
  return (
    <>
      {workspace.error ? (
        <ErrorState title="The run failed" message={workspace.error} />
      ) : null}
      <ol aria-label="Stages" className="flex min-w-0 flex-col">
        {STAGES.map((stage, index) => (
          <StageRow
            key={stage}
            label={STAGE_LABEL[stage]}
            state={states[stage]}
            activity={activity.get(stage)}
            last={index === STAGES.length - 1}
          />
        ))}
      </ol>
    </>
  );
}
