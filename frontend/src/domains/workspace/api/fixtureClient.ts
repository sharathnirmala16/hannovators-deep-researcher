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

export const fixtureClient: WorkspaceClient = {
  source: 'fixtures',
  defaultWorkspaceId: async () =>
    (await loadFixtures())[0]?.state.workspace.id ?? null,
  getWorkspace: async (id) => (await findFixture(id)).state,
  getGraph: async (id) => (await findFixture(id)).graph,
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
