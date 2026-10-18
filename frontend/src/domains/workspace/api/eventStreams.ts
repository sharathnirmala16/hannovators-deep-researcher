import type {
  TrajectoryStreamHandlers,
  WorkspaceEventHandlers,
} from './contract';
import { trajectoryStepSummarySchema } from './auditSchema';
import { traceEventSchema } from './schema';

export const workspacePath = (id: string) =>
  `/api/workspaces/${encodeURIComponent(id)}`;

export function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

/** Trace events (`event: trace`). EventSource resends Last-Event-ID itself. */
export function subscribeEvents(
  id: string,
  { onEvent, onEnd, onError }: WorkspaceEventHandlers,
): () => void {
  const source = new EventSource(`${workspacePath(id)}/events`);
  source.addEventListener('trace', (message: MessageEvent<string>) => {
    const event = traceEventSchema.safeParse(parseJson(message.data));
    if (event.success) onEvent(event.data);
    else onError(new Error(`Invalid trace event: ${event.error.message}`));
  });
  source.addEventListener('end', () => {
    source.close();
    onEnd();
  });
  source.addEventListener('error', () => {
    onError(new Error('The event stream was interrupted.'));
  });
  return () => source.close();
}

/** Trajectory steps (`event: step`); a step is resent when its status changes. */
export function subscribeTrajectory(
  id: string,
  { onStep, onError }: TrajectoryStreamHandlers,
): () => void {
  const source = new EventSource(`${workspacePath(id)}/trajectory/stream`);
  source.addEventListener('step', (message: MessageEvent<string>) => {
    const step = trajectoryStepSummarySchema.safeParse(parseJson(message.data));
    if (step.success) onStep(step.data);
    else onError(new Error(`Invalid trajectory step: ${step.error.message}`));
  });
  source.addEventListener('error', () => {
    onError(new Error('The trajectory stream was interrupted.'));
  });
  return () => source.close();
}
