---
name: "frontend-unit-test-skill"
description: "Write, run, and debug fast unit tests with Vitest and React Testing Library in frontend/src. Use when you verify wire decoders, the workspace SSE event reducer, or pure helpers, mock asynchronous adapters, or fix unit test failures."
---

# Vitest Unit & Component Testing

Fast unit testing of `frontend/src` with Vitest, React Testing Library, and jsdom.

> **Hackathon scope**: Follow the **Hackathon Test Policy** in `frontend-code-structure` (Section 5). Write tests only for edge cases in wire decoders, the SSE event reducer, and pure helpers with boundaries. No component snapshot tests, no layout/styling tests, no coverage targets. Run `pnpm test` only when test files exist.

## 1. Execution Path: Choose the Lightest Path

Run each command from `frontend/`.

* **Inner Loop (Active Development)**: Run only the specific test file:
  ```bash
  pnpm exec vitest run src/domains/workspace/model/workspaceEventReducer.test.ts
  ```
* **Interactive Watch Mode**:
  ```bash
  pnpm test:watch
  ```
* **Full Suite**:
  ```bash
  pnpm test               # vitest run, once
  ```
* **Coverage**: Not configured. There is no `test:coverage` script and no coverage provider dependency. Do not add one during the hackathon.

---

## 2. Test Configuration (`vitest.config.ts`)

`vitest.config.ts` merges `vite.config.ts`:

* Vitest uses its default include globs, so colocated `*.test.ts(x)` files under `src/` run (the globs also match `*.spec.ts` outside `src/`; exclude `tests/**` when the Phase 3 Playwright spec lands).
* The suite runs in the `jsdom` environment and loads the setup file `./src/test/setup.ts`.
* `clearMocks` and `restoreMocks` are on, so mocks reset between tests.
* The `@` alias (from `vite.config.ts`) resolves to `./src`.
* Shared helpers and recorded fixtures live in `src/test/` (fixtures in `src/test/fixtures/`).

---

## 3. Core Testing Patterns

### 1. Wire Decoder Edge Case (zod)
Decoders live in `domains/workspace/api/`. Test malformed and missing fields, not the happy path alone. (`zod` is planned in `PLAN.md`; add it with `pnpm add zod` when the first decoder lands.)

```typescript
import { describe, it, expect } from 'vitest';
import { decodeTraceEvent } from './traceEventDecoder';

describe('decodeTraceEvent', () => {
  it('rejects an event with an unknown kind', () => {
    const result = decodeTraceEvent({ id: 'evt-1', kind: 'teleport', at: '2025-01-01T00:00:00Z' });
    expect(result.success).toBe(false);
  });

  it.each([
    ['missing id', { kind: 'search_started', at: '2025-01-01T00:00:00Z' }],
    ['non-string at', { id: 'evt-2', kind: 'search_started', at: 42 }],
  ])('rejects a payload with %s', (_label, payload) => {
    expect(decodeTraceEvent(payload).success).toBe(false);
  });
});
```

### 2. SSE Event Reducer Edge Case
The reducer in `domains/workspace/model/` must stay idempotent across duplicates, out-of-order delivery, and resume.

```typescript
import { describe, it, expect } from 'vitest';
import { initialWorkspaceState, workspaceEventReducer } from './workspaceEventReducer';

const event = { id: 'evt-7', seq: 7, kind: 'source_found', sourceId: 'src-1' } as const;

describe('workspaceEventReducer', () => {
  it('ignores a duplicate event id', () => {
    const once = workspaceEventReducer(initialWorkspaceState, event);
    const twice = workspaceEventReducer(once, event);

    expect(twice).toBe(once);
    expect(twice.trace).toHaveLength(1);
  });
});
```

### 3. React Component Test (only when justified)
Under the hackathon policy, test a component only for behavior that a pure helper cannot cover. Query by role and label.

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '@/shared/ui/button'; // shadcn primitive, once added

describe('Button', () => {
  it('triggers onClick handler on user click', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    render(<Button onClick={handleClick}>Start run</Button>);

    await user.click(screen.getByRole('button', { name: 'Start run' }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

### 4. Async Generator Stream Mocking
```typescript
// Mock an SSE-like async stream of workspace events
const mockStream = vi.fn().mockImplementation(async function* () {
  yield { id: 'evt-1', seq: 1, kind: 'search_started' };
  yield { id: 'evt-2', seq: 2, kind: 'source_found', sourceId: 'src-1' };
});
```

---

## 4. Troubleshoot Predictably

| Symptom | Cause | Action |
| :--- | :--- | :--- |
| **`ReferenceError: document is not defined`** | DOM test running outside jsdom | Keep `environment: 'jsdom'` in `vitest.config.ts`, or add `// @vitest-environment jsdom` at the top of the file. |
| **Unresolved alias `@/...`** | The alias map is absent or wrong | Verify that the `@` alias in `vite.config.ts` points to `./src` and `tsconfig.json` has the matching `paths`. |
| **`No test files found`** | The suite is empty | Expected before the first real test. Do not add an artificial test; skip `pnpm test` until test files exist. |
| **Flaky async / unhandled promise rejection** | An async action is not awaited | Use `await` for each async call in the test block. |
| **Generator mock produces no items** | Mock function returned an array instead of an async iterable | Use `async function* () { yield ... }` to mock streaming contracts. |

---

## 5. Best Practices & Rules

- **Isolate Unit Tests**: Never make real network calls in unit tests; use `vi.fn()`, typed adapters, and fixtures from `src/test/fixtures/`.
- **Behavior over Implementation**: Assert inputs, outputs, and user-observable state changes rather than internal private variables.
- **Edge Cases First**: Prefer `it.each` tables of malformed, missing, duplicate, and out-of-order inputs.
- **Coverage Guidance**: No coverage target during the hackathon.
