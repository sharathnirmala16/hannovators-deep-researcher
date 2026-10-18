import { describe, expect, it } from 'vitest';

import {
  graphViewSchema,
  traceEventSchema,
  workspaceStateSchema,
} from './schema';

const fixtures = import.meta.glob<unknown>('/src/test/fixtures/*.json', {
  eager: true,
  import: 'default',
});

function fixture(name: string): unknown {
  const data = fixtures[`/src/test/fixtures/${name}.json`];
  expect(data, `fixture ${name}.json`).toBeDefined();
  return data;
}

describe('workspace contract schema', () => {
  it.each(['medical', 'general'])('accepts the %s fixtures', (mode) => {
    const state = workspaceStateSchema.safeParse(fixture(`workspace.${mode}`));
    const graph = graphViewSchema.safeParse(fixture(`graph.${mode}`));

    expect(state.error).toBeUndefined();
    expect(graph.error).toBeUndefined();
  });

  it('rejects an unknown TraceEventKind', () => {
    const event = {
      id: 7,
      workspace_id: '3b7e9a4c-1d2f-4e6a-8b5c-0f9d2a7c6e11',
      stage: 'screen',
      kind: 'TELEPORT',
      message: 'Screened 38 candidates',
      payload: {},
      created_at: '2026-10-18T09:16:02Z',
    };

    const result = traceEventSchema.safeParse(event);

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path)).toEqual([['kind']]);
  });
});
