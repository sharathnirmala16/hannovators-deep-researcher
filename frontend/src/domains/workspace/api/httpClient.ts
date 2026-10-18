import type { z } from 'zod';

import {
  WorkspaceApiError,
  type WorkspaceClient,
  type WorkspaceEventHandlers,
} from './contract';
import {
  apiErrorSchema,
  createWorkspaceRequestSchema,
  graphViewSchema,
  traceEventSchema,
  workspaceStateSchema,
  workspaceViewSchema,
} from './schema';

const workspacePath = (id: string) =>
  `/api/workspaces/${encodeURIComponent(id)}`;

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

/** Normalizes a failed response, using the `ApiError` body when present. */
async function toApiError(response: Response): Promise<WorkspaceApiError> {
  const body = apiErrorSchema.safeParse(parseJson(await response.text()));
  if (body.success) {
    const { code, message } = body.data.detail;
    return new WorkspaceApiError(response.status, code, message);
  }
  const message = `${response.status} ${response.statusText}`.trim();
  return new WorkspaceApiError(response.status, 'HTTP_ERROR', message);
}

async function send(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(path, init);
  if (!response.ok) throw await toApiError(response);
  return response;
}

async function request<S extends z.ZodType>(
  path: string,
  schema: S,
  init: RequestInit = {},
): Promise<z.output<S>> {
  const response = await send(path, init);
  const decoded = schema.safeParse(parseJson(await response.text()));
  if (!decoded.success) {
    throw new WorkspaceApiError(
      response.status,
      'INVALID_RESPONSE',
      `Unexpected response from ${path}: ${decoded.error.message}`,
    );
  }
  return decoded.data;
}

function subscribeEvents(
  id: string,
  { onEvent, onEnd, onError }: WorkspaceEventHandlers,
): () => void {
  // EventSource reconnects by itself and sends Last-Event-ID on reconnect.
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

export const httpClient: WorkspaceClient = {
  source: 'http',
  defaultWorkspaceId: () => Promise.resolve(null),
  getWorkspace: (id, signal) =>
    request(workspacePath(id), workspaceStateSchema, {
      signal: signal ?? null,
    }),
  getGraph: (id, signal) =>
    request(`${workspacePath(id)}/graph`, graphViewSchema, {
      signal: signal ?? null,
    }),
  createWorkspace: (body) =>
    request('/api/workspaces', workspaceViewSchema, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(createWorkspaceRequestSchema.parse(body)),
    }),
  runWorkspace: async (id) => {
    await send(`${workspacePath(id)}/run`, { method: 'POST' });
  },
  subscribeEvents,
};
