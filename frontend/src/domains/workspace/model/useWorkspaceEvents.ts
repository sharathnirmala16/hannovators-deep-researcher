import { useEffect, useState } from 'react';

import type { WorkspaceClient } from '../api/contract';
import type { TraceEvent } from '../api/schema';

export type EventStreamStatus = 'idle' | 'open' | 'ended' | 'error';

export interface WorkspaceEvents {
  events: readonly TraceEvent[];
  status: EventStreamStatus;
}

interface StreamState extends WorkspaceEvents {
  key: string | null;
}

type StreamAction =
  { type: 'event'; event: TraceEvent } | { type: 'end' } | { type: 'error' };

const IDLE: WorkspaceEvents = { events: [], status: 'idle' };
const OPENING: WorkspaceEvents = { events: [], status: 'open' };

/** Inserts by ID: repeated IDs are ignored and late events land in order. */
function insertEvent(
  events: readonly TraceEvent[],
  event: TraceEvent,
): readonly TraceEvent[] {
  if (events.some((item) => item.id === event.id)) return events;
  const last = events[events.length - 1];
  if (!last || last.id < event.id) return [...events, event];
  return [...events, event].sort((a, b) => a.id - b.id);
}

function reduceStream(
  state: StreamState,
  key: string,
  action: StreamAction,
): StreamState {
  // A reconnect keeps the events already received (same workspace).
  const sameWorkspace = state.key?.split('#')[0] === key.split('#')[0];
  const base = sameWorkspace
    ? { ...state, key }
    : { ...OPENING, key, events: [] };
  switch (action.type) {
    case 'event': {
      const events = insertEvent(base.events, action.event);
      return { ...base, status: 'open', events };
    }
    case 'end':
      return { ...base, status: 'ended' };
    case 'error':
      return { ...base, status: 'error' };
  }
}

/**
 * Subscribes to the trace events of one workspace. Changing `connection`
 * opens the stream again (for example after the run continues), keeping
 * the events already received.
 */
export function useWorkspaceEvents(
  client: WorkspaceClient,
  workspaceId: string | null,
  connection = 0,
): WorkspaceEvents {
  const [stream, setStream] = useState<StreamState>({ ...IDLE, key: null });

  useEffect(() => {
    if (!workspaceId) return undefined;
    const key = `${workspaceId}#${connection}`;
    const dispatch = (action: StreamAction) =>
      setStream((state) => reduceStream(state, key, action));
    return client.subscribeEvents(workspaceId, {
      onEvent: (event) => dispatch({ type: 'event', event }),
      onEnd: () => dispatch({ type: 'end' }),
      onError: () => dispatch({ type: 'error' }),
    });
  }, [client, workspaceId, connection]);

  if (!workspaceId) return IDLE;
  const sameWorkspace = stream.key?.split('#')[0] === workspaceId;
  return sameWorkspace ? stream : OPENING;
}
