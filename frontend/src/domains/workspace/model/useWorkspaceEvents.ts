import { useEffect, useState } from 'react';

import type { WorkspaceClient } from '../api/contract';
import type { TraceEvent } from '../api/schema';

export type EventStreamStatus = 'idle' | 'open' | 'ended' | 'error';

export interface WorkspaceEvents {
  events: readonly TraceEvent[];
  status: EventStreamStatus;
}

interface StreamState extends WorkspaceEvents {
  workspaceId: string | null;
}

type StreamAction =
  { type: 'event'; event: TraceEvent } | { type: 'end' } | { type: 'error' };

const IDLE: WorkspaceEvents = { events: [], status: 'idle' };
const OPENING: WorkspaceEvents = { events: [], status: 'open' };

/**
 * Stub reducer: appends new events and ignores repeated IDs. Lane F1 replaces
 * it with the full event reducer (out-of-order delivery, resume).
 */
function reduceStream(
  state: StreamState,
  workspaceId: string,
  action: StreamAction,
): StreamState {
  const base =
    state.workspaceId === workspaceId ? state : { ...OPENING, workspaceId };
  switch (action.type) {
    case 'event':
      if (base.events.some((event) => event.id === action.event.id)) {
        return base;
      }
      return {
        ...base,
        status: 'open',
        events: [...base.events, action.event],
      };
    case 'end':
      return { ...base, status: 'ended' };
    case 'error':
      return { ...base, status: 'error' };
  }
}

/** Subscribes to the trace event stream of one workspace (SSE hook stub). */
export function useWorkspaceEvents(
  client: WorkspaceClient,
  workspaceId: string | null,
): WorkspaceEvents {
  const [stream, setStream] = useState<StreamState>({
    ...IDLE,
    workspaceId: null,
  });

  useEffect(() => {
    if (!workspaceId) return undefined;
    const dispatch = (action: StreamAction) =>
      setStream((state) => reduceStream(state, workspaceId, action));
    return client.subscribeEvents(workspaceId, {
      onEvent: (event) => dispatch({ type: 'event', event }),
      onEnd: () => dispatch({ type: 'end' }),
      onError: () => dispatch({ type: 'error' }),
    });
  }, [client, workspaceId]);

  if (!workspaceId) return IDLE;
  return stream.workspaceId === workspaceId ? stream : OPENING;
}
