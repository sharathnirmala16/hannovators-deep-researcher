---
name: frontend-bdd-test-skill
description: "Reference for end-to-end browser tests of the frontend/ React app. During the hackathon only one plain @playwright/test smoke test (Phase 3, fixture mode) is planned; Playwright-BDD, Gherkin, and bddgen are deferred. Use when adding the smoke test, running browser tests, diagnosing E2E failures, or planning post-hackathon BDD scenarios."
---

# Playwright-BDD for React & TypeScript

> **Status (hackathon): Playwright-BDD / Gherkin is deferred.**
> - Playwright is **not installed** yet.
> - Phase 3 of `PLAN.md` adds a **single plain `@playwright/test` smoke test** for the demo path, run against fixture mode (`VITE_USE_FIXTURES=1`). No `playwright-bdd`, no `bddgen`, no `.feature` files.
> - Follow the **Hackathon Test Policy** in `frontend-code-structure` (Section 5).
> - Keep the rest of this document as reference for after the hackathon. The `pnpm bddgen` and `pnpm test:e2e*` scripts below do not exist yet.

End-to-end Behavior-Driven Development (BDD) using `playwright-bdd`, TypeScript, and Gherkin (`.feature`) files.

## 0. Phase 3 Smoke Test (hackathon)

Run from `frontend/` after Phase 3 installs Playwright (`pnpm add -D @playwright/test`):

```typescript
// frontend/tests/smoke.spec.ts
import { test, expect } from '@playwright/test';

test('demo path renders a fixture workspace', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /workbench/i })).toBeVisible();
});
```

```bash
pnpm exec playwright test
```

Configure `playwright.config.ts` `webServer` to start Vite with `VITE_USE_FIXTURES=1` on the worktree's `VITE_PORT`. Keep the spec outside `src/`, and add `tests/**` to `test.exclude` in `vitest.config.ts` (merged with Vitest's default excludes), because Vitest's default include globs also match `*.spec.ts` files outside `src/`.

---

## 1. Workflow & Commands (post-hackathon reference)

Run each command from `frontend/`.

**Workflow**: Write `.feature` ──> Implement step definitions in `tests/steps/*.ts` ──> `pnpm bddgen` ──> `pnpm test:e2e`

Run `pnpm bddgen` before each direct `pnpm exec playwright test` command. The generated specs in `tests/features-gen/` must agree with the current `.feature` files.

* **Inner Loop (Active Development)**: Run only the scenario under test:
  ```bash
  pnpm bddgen && pnpm exec playwright test --grep "@smoke"
  ```
* **Full Suite Execution**:
  ```bash
  pnpm test:e2e          # Runs bddgen and executes full test matrix
  pnpm test:e2e:headed   # Runs bddgen and executes the matrix in headed mode
  ```
* **Debugging**:
  ```bash
  pnpm exec playwright test --debug
  pnpm exec playwright show-report
  ```

---

## 2. Directory Structure (`frontend`, post-hackathon reference)

```
frontend/
├── playwright.config.ts          # defineBddConfig & webServer config
└── tests/
    ├── features/                 # Declarative Gherkin (.feature) files
    ├── features-gen/             # Generated specs from bddgen (never edit by hand)
    └── steps/                    # Step definitions & fixtures
        ├── fixtures.ts           # Extended Playwright test & createBdd export
        └── *.steps.ts            # Typed Given, When, Then definitions
```

---

## 3. Implementation Patterns (post-hackathon reference)

### Centralized Fixtures (`tests/steps/fixtures.ts`)
```typescript
import { test as base, createBdd } from "playwright-bdd";

export const test = base.extend<{ /* custom Page Objects / fixtures */ }>({
  // fixture implementations
});

export const { Given, When, Then, Step, Before, After, BeforeAll, AfterAll } =
  createBdd(test);
```

### Declarative Gherkin (`tests/features/workbench.feature`)
```gherkin
Feature: Research Workbench
  Background:
    Given I open the workbench in fixture mode

  @smoke
  Scenario: Reviewing the screening funnel of a recorded workspace
    When I switch to "Medical EBM" mode
    Then the screening funnel shows the excluded record count
```

### TypeScript Step Definitions (`tests/steps/workbench.steps.ts`)
```typescript
import { expect } from "@playwright/test";
import { Given, When, Then } from "./fixtures";

Given("I open the workbench in fixture mode", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("main")).toBeVisible();
});

When("I switch to {string} mode", async ({ page }, mode: string) => {
  await page.getByRole("radio", { name: mode }).check();
});

Then("the screening funnel shows the excluded record count", async ({ page }) => {
  await expect(page.getByRole("region", { name: /screening funnel/i })).toContainText(/excluded/i);
});
```

---

## 4. Troubleshoot Predictably

| Symptom | Cause | Action |
| :--- | :--- | :--- |
| **"Missing step definition" error** | Gherkin text does not match step pattern or `bddgen` not regenerated | Run `pnpm bddgen` to regenerate `tests/features-gen/`; check parameter quotes `{string}` vs `{int}`. |
| **Flaky or timing out element** | Using fixed `waitForTimeout` or missing auto-wait assertion | Use auto-waiting assertions: `await expect(locator).toBeVisible()` or semantic `page.getByRole(...)`. |
| **Port busy or connection refused** | A dev server uses the port, or no dev server runs | Do the worktree port check and the server identity check in Section 5. |
| **Smoke test hits the real backend** | Fixture mode is off | Start Vite with `VITE_USE_FIXTURES=1` in the Playwright `webServer` command. |
| **Stale test runner artifacts** | Cached `tests/features-gen/` specs from deleted feature files | Delete the `tests/features-gen/` directory and re-run `pnpm bddgen`. |

---

## 5. Best Practices & Rules

- **Declarative Scenarios**: Write user-intent focused scenarios (`When I start a General Research run`), not low-level DOM keystrokes.
- **Auto-Waiting Locators**: Rely on auto-waiting assertions (`await expect(locator).toBeVisible()`). Never use hardcoded sleeps (`page.waitForTimeout()`).
- **Worktree Port Check**: Each git worktree uses its own `VITE_PORT` and `API_PORT` from its local `.env`. Read both before you start a server, and confirm that the ports belong to your worktree.
- **Server Identity Check**: Confirm the identity of each running server. Run e2e tests only against the server of your own worktree.
- **Clean Git Artifacts**: Keep `tests/features-gen/`, `test-results/`, and `playwright-report/` in `.gitignore`.
