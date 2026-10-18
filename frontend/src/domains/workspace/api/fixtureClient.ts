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
  getTrajectory: () =>
    Promise.resolve({ steps: [], next_after: null, total: 0 }),
  getTrajectoryStep: () => notInFixtures('Trajectory detail'),
  subscribeTrajectory: () => () => undefined,
  recordAction: () => Promise.resolve(),
  listChat: () => Promise.resolve([]),
  ask: () => notInFixtures('Chat'),
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
