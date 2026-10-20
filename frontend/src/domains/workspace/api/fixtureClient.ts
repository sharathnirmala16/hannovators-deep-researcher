import { chatMessageViewSchema, type ChatMessageView } from './auditSchema';
import { WorkspaceApiError, type WorkspaceClient } from './contract';
import {
  graphViewSchema,
  workspaceStateSchema,
  type GraphView,
  type WorkspaceState,
} from './schema';

/**
 * Fixture mode (`VITE_USE_FIXTURES=1`): serves the recorded workspaces in
 * `src/test/fixtures/`. The glob loads each JSON file lazily, so the fixtures
 * stay out of the main bundle, and features cannot import them directly.
 */
const loaders = import.meta.glob<unknown>('/src/test/fixtures/*.json', {
  import: 'default',
});

/** The first fixture is the default workspace. */
const FIXTURE_NAMES = ['medical', 'general'] as const;

interface FixtureWorkspace {
  name: string;
  state: WorkspaceState;
  graph: GraphView;
}

async function loadJson(name: string): Promise<unknown> {
  const load = loaders[`/src/test/fixtures/${name}.json`];
  if (!load) throw new Error(`Fixture ${name}.json is missing.`);
  return load();
}

async function loadFixture(name: string): Promise<FixtureWorkspace> {
  const [state, graph] = await Promise.all([
    loadJson(`workspace.${name}`),
    loadJson(`graph.${name}`),
  ]);
  return {
    name,
    state: workspaceStateSchema.parse(state),
    graph: graphViewSchema.parse(graph),
  };
}

let fixtures: Promise<FixtureWorkspace[]> | undefined;

function loadFixtures(): Promise<FixtureWorkspace[]> {
  fixtures ??= Promise.all(FIXTURE_NAMES.map(loadFixture));
  return fixtures;
}

async function findFixture(id: string): Promise<FixtureWorkspace> {
  const found = (await loadFixtures()).find(
    (fixture) => fixture.state.workspace.id === id,
  );
  if (!found) {
    throw new WorkspaceApiError(
      404,
      'WORKSPACE_NOT_FOUND',
      `No fixture workspace has the ID ${id}.`,
    );
  }
  return found;
}

/** Chat turns asked in this session, per workspace (fixtures are read-only). */
const chatHistory = new Map<string, ChatMessageView[]>();
const FIXTURE_ANSWER_MS = 1500;
let chatSequence = 0;

function chatMessage(
  workspaceId: string,
  role: ChatMessageView['role'],
  body: unknown,
): ChatMessageView {
  chatSequence += 1;
  return chatMessageViewSchema.parse({
    ...(body as object),
    id: `fixture-chat-${chatSequence}`,
    workspace_id: workspaceId,
    role,
    created_at: new Date().toISOString(),
  });
}

/** The canned cited answer in `chat.<name>.json`, after a short delay. */
async function fixtureAnswer(
  id: string,
  question: string,
): Promise<ChatMessageView> {
  const { name } = await findFixture(id);
  const asked = chatMessage(id, 'USER', { content: question });
  const canned = await loadJson(`chat.${name}`);
  await new Promise((resolve) => setTimeout(resolve, FIXTURE_ANSWER_MS));
  const answer = chatMessage(id, 'ASSISTANT', canned);
  chatHistory.set(id, [...(chatHistory.get(id) ?? []), asked, answer]);
  return answer;
}

const notInFixtures = (what: string) =>
  Promise.reject(
    new WorkspaceApiError(
      501,
      'NOT_IN_FIXTURES',
      `${what} needs the live API.`,
    ),
  );

export const fixtureClient: WorkspaceClient = {
  source: 'fixtures',
  defaultWorkspaceId: async () =>
    (await loadFixtures())[0]?.state.workspace.id ?? null,
  listWorkspaces: async () =>
    (await loadFixtures()).map(({ state }) => ({
      id: state.workspace.id,
      research_question: state.workspace.research_question,
      domain_mode: state.workspace.domain_mode,
      status: state.workspace.status,
      current_stage: state.workspace.current_stage,
      created_at: state.workspace.created_at,
      updated_at: state.workspace.updated_at,
      source_count: state.sources.length,
      promoted_count: state.funnel.appraise_promoted,
      seed_count: state.funnel.seeds,
    })),
  getWorkspace: async (id) => (await findFixture(id)).state,
  getGraph: async (id) => (await findFixture(id)).graph,
  uploadSeedFiles: () => notInFixtures('Seed upload'),
  addSeedReference: () => notInFixtures('Seed references'),
  updateDecomposition: async (id) => (await findFixture(id)).state,
  getSource: () => notInFixtures('Source detail'),
  decideSource: () => notInFixtures('Including or excluding a source'),
  resynthesize: () => notInFixtures('Re-synthesis'),
  getTrajectory: () =>
    Promise.resolve({ steps: [], next_after: null, total: 0 }),
  getTrajectoryStep: () => notInFixtures('Trajectory detail'),
  subscribeTrajectory: () => () => undefined,
  recordAction: () => Promise.resolve(),
  listChat: (id) => Promise.resolve([...(chatHistory.get(id) ?? [])]),
  ask: fixtureAnswer,
  startDeepResearch: () => notInFixtures('Deep research'),
  getDeepResearch: () => Promise.resolve(null),
  createWorkspace: async (body) => {
    const mode = body.domain_mode === 'GENERAL' ? 'GENERAL' : 'MEDICAL';
    const all = await loadFixtures();
    const match = all.find(
      (fixture) => fixture.state.decomposition?.mode === mode,
    );
    const fixture = match ?? all[0];
    if (!fixture) throw new Error('No fixture workspaces are available.');
    return fixture.state.workspace;
  },
  runWorkspace: () => Promise.resolve(),
  subscribeEvents: (_id, { onEnd }) => {
    // Fixtures hold a completed run, so the stream ends at once.
    queueMicrotask(onEnd);
    return () => undefined;
  },
};
