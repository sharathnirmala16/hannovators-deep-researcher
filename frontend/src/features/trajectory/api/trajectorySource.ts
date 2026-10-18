import type {
  TrajectoryPage,
  TrajectoryQuery,
  TrajectoryStep,
  TrajectoryStreamHandlers,
  UserActionRequest,
  WorkspaceClient,
} from '@/domains/workspace';

import { fixturePage, fixtureStream, fixtureSteps } from './fixtureTrajectory';

/** The trajectory calls of one workspace. */
export interface TrajectorySource {
  workspaceId: string;
  list: (
    query: TrajectoryQuery,
    signal: AbortSignal,
  ) => Promise<TrajectoryPage>;
  step: (stepId: number, signal: AbortSignal) => Promise<TrajectoryStep>;
  subscribe: (handlers: TrajectoryStreamHandlers) => () => void;
  /** Best effort; never throws. */
  record: (action: UserActionRequest) => void;
}

function clientSource(
  client: WorkspaceClient,
  workspaceId: string,
): TrajectorySource {
  return {
    workspaceId,
    list: (query, signal) => client.getTrajectory(workspaceId, query, signal),
    step: (stepId, signal) =>
      client.getTrajectoryStep(workspaceId, stepId, signal),
    subscribe: (handlers) => client.subscribeTrajectory(workspaceId, handlers),
    record: (action) => void client.recordAction(workspaceId, action),
  };
}

/** Serves the recorded fixture when one exists, else the client. */
function fixtureSource(base: TrajectorySource): TrajectorySource {
  const steps = fixtureSteps(base.workspaceId);
  return {
    ...base,
    list: async (query, signal) => {
      const recorded = await steps;
      return recorded ? fixturePage(recorded, query) : base.list(query, signal);
    },
    step: async (stepId, signal) => {
      const found = (await steps)?.find((step) => step.id === stepId);
      return found ?? base.step(stepId, signal);
    },
    subscribe: (handlers) => {
      let close: () => void = () => undefined;
      let closed = false;
      void steps.then((recorded) => {
        if (closed) return;
        close = recorded
          ? fixtureStream(recorded, handlers)
          : base.subscribe(handlers);
      });
      return () => {
        closed = true;
        close();
      };
    },
  };
}

export function trajectorySource(
  client: WorkspaceClient,
  workspaceId: string,
): TrajectorySource {
  const base = clientSource(client, workspaceId);
  return client.source === 'fixtures' ? fixtureSource(base) : base;
}
