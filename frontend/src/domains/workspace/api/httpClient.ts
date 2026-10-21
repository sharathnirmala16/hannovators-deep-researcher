import { z } from 'zod';

import {
  WorkspaceApiError,
  type TrajectoryQuery,
  type WorkspaceClient,
} from './contract';
import {
  parseJson,
  subscribeEvents,
  subscribeTrajectory,
  workspacePath,
} from './eventStreams';
import {
  chatMessageViewSchema,
  chatRequestSchema,
  deepResearchRecordSchema,
  sourceDetailSchema,
  trajectoryPageSchema,
  trajectoryStepSchema,
  userActionRequestSchema,
  workspaceSummarySchema,
} from './auditSchema';
import {
  apiErrorSchema,
  createWorkspaceRequestSchema,
  decompositionSchema,
  graphViewSchema,
  seedReferenceRequestSchema,
  sourceDecisionRequestSchema,
  sourceViewSchema,
  workspaceStateSchema,
  workspaceViewSchema,
} from './schema';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

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

const withSignal = (signal?: AbortSignal): RequestInit => ({
  signal: signal ?? null,
});

const postJson = (body: unknown, method = 'POST'): RequestInit => ({
  method,
  headers: JSON_HEADERS,
  body: JSON.stringify(body),
});

function trajectoryPath(id: string, query: TrajectoryQuery = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  const search = params.toString();
  return `${workspacePath(id)}/trajectory${search ? `?${search}` : ''}`;
}

const sourceList = z.array(sourceViewSchema);

export const httpClient: WorkspaceClient = {
  source: 'http',
  defaultWorkspaceId: () => Promise.resolve(null),
  listWorkspaces: (signal) =>
    request(
      '/api/workspaces',
      z.array(workspaceSummarySchema),
      withSignal(signal),
    ),
  getWorkspace: (id, signal) =>
    request(workspacePath(id), workspaceStateSchema, withSignal(signal)),
  getGraph: (id, signal) =>
    request(`${workspacePath(id)}/graph`, graphViewSchema, withSignal(signal)),
  createWorkspace: (body) =>
    request(
      '/api/workspaces',
      workspaceViewSchema,
      postJson(createWorkspaceRequestSchema.parse(body)),
    ),
  deleteWorkspace: async (id) => {
    await send(workspacePath(id), { method: 'DELETE' });
  },
  uploadSeedFiles: (id, files) => {
    const form = new FormData();
    for (const file of files) form.append('files', file);
    return request(`${workspacePath(id)}/seeds`, sourceList, {
      method: 'POST',
      body: form,
    });
  },
  addSeedReference: (id, body) =>
    request(
      `${workspacePath(id)}/seeds`,
      sourceList,
      postJson(seedReferenceRequestSchema.parse(body)),
    ),
  runWorkspace: async (id) => {
    await send(`${workspacePath(id)}/run`, { method: 'POST' });
  },
  updateDecomposition: (id, decomposition) =>
    request(
      `${workspacePath(id)}/decomposition`,
      workspaceStateSchema,
      postJson(decompositionSchema.parse(decomposition), 'PUT'),
    ),
  getSource: (id, sourceId, signal) =>
    request(
      `${workspacePath(id)}/sources/${encodeURIComponent(sourceId)}`,
      sourceDetailSchema,
      withSignal(signal),
    ),
  decideSource: (id, sourceId, body) =>
    request(
      `${workspacePath(id)}/sources/${encodeURIComponent(sourceId)}/decision`,
      workspaceStateSchema,
      postJson(sourceDecisionRequestSchema.parse(body)),
    ),
  resynthesize: async (id) => {
    await send(`${workspacePath(id)}/resynthesize`, { method: 'POST' });
  },
  subscribeEvents,
  getTrajectory: (id, query, signal) =>
    request(
      trajectoryPath(id, query),
      trajectoryPageSchema,
      withSignal(signal),
    ),
  getTrajectoryStep: (id, stepId, signal) =>
    request(
      `${workspacePath(id)}/trajectory/${stepId}`,
      trajectoryStepSchema,
      withSignal(signal),
    ),
  subscribeTrajectory,
  recordAction: async (id, action) => {
    try {
      await send(
        `${workspacePath(id)}/trajectory/actions`,
        postJson(userActionRequestSchema.parse(action)),
      );
    } catch {
      // Best effort: a failed audit write must never break the UI action.
    }
  },
  listChat: (id, signal) =>
    request(
      `${workspacePath(id)}/chat`,
      z.array(chatMessageViewSchema),
      withSignal(signal),
    ),
  ask: (id, question) =>
    request(
      `${workspacePath(id)}/chat`,
      chatMessageViewSchema,
      postJson(chatRequestSchema.parse({ question })),
    ),
  startDeepResearch: (id) =>
    request(`${workspacePath(id)}/deep-research`, deepResearchRecordSchema, {
      method: 'POST',
    }),
  getDeepResearch: async (id, signal) => {
    try {
      return await request(
        `${workspacePath(id)}/deep-research`,
        deepResearchRecordSchema,
        withSignal(signal),
      );
    } catch (error) {
      if (error instanceof WorkspaceApiError && error.status === 404)
        return null;
      throw error;
    }
  },
};
