---
name: frontend-code-structure
description: "Guidelines and conventions for frontend/src module boundaries, feature/domain separation, component extraction, state management, layer conventions, the hackathon test policy, and test organization. Use when you create UI components, refactor React code, structure features, or audit frontend boundaries."
---

# Frontend Code Structure & Architecture Guidelines

A modular, feature-and-domain driven React architecture for the Adaptive Deep Research & Evidence Synthesis Workbench. It prevents monolithic contexts, keeps strict dependency boundaries, and supports sustainable component growth.

Stack: React 19, Vite, TypeScript, Tailwind v4, shadcn (primitives in `frontend/src/shared/ui/`), Vitest + React Testing Library + jsdom, pnpm.

---

## 1. Target Architectural Layers & Responsibilities (`frontend/src/`)

```text
src/
  app/                   # Bootstrap, shell, provider composition, adaptive GenUI composition
    App.tsx              # Composes features from the backend's `ui_components` list
  domains/               # Core business models, data ownership, and domain APIs
    workspace/           # Wire types, zod decoders, API calls, SSE event reducer for one research workspace
    evidence/            # Sources, claims, GRADE rows, highlight mappers
  features/              # User-facing feature modules (screen sections and workflows)
    workbench-shell/     # 3-pane layout, run creation, Medical EBM / General Research mode toggle, live trace timeline
    scope-builder/       # PICOTS chips / research scope chips
    screening-funnel/    # PRISMA-style funnel + rejection audit
    evidence-table/      # GRADE evidence profile table + due-diligence claim matrix
    pdf-viewer/          # Highlighted PDF iframe at `#page=N`
    citation-graph/      # react-force-graph citation graph
  shared/                # Business-agnostic, reusable primitives and infrastructure
    ui/                  # shadcn primitives and dumb UI components (Button, Dialog, Tabs)
    api/                 # HTTP/SSE client abstraction, fetch error normalization
    lib/                 # Generic utility helpers (`cn`, date formatting)
  test/                  # Shared test helpers, setup, and recorded fixtures
    fixtures/            # Recorded workspace JSON served in fixture mode
```

This layout is the target architecture (see `PLAN.md`). Parts of it are not in place yet. Treat each path in this section as the goal for new code.

**Fixture mode**: `VITE_USE_FIXTURES=1` serves a recorded workspace JSON from `frontend/src/test/fixtures/` so features can be built without the backend. Wire the switch at the `app/` or `domains/workspace` API boundary; features must not know which source is active.

### Layer Ownership Matrix

| Layer | Responsibility | What It May Import | What Must Never Enter |
| :--- | :--- | :--- | :--- |
| **`app/`** | Shell composition, adaptive feature selection from `ui_components`, root providers. | `features/`, `domains/`, `shared/` | Feature-internal private helpers |
| **`features/`** | User workflows, panes, cohesive dialogs. | `domains/` (public API), `shared/` | **Other `features/`** (no feature-to-feature imports) |
| **`domains/`** | Business logic, decoders, reducers, wire-to-domain mappers. | `shared/` | `features/`, `app/`, other `domains/` (by default) |
| **`shared/ui`** | Pure design-system components and accessible primitives. | Other `shared/` primitives | Business models, domain types, API clients |
| **`shared/api`** | Transport setup, status codes, abort signals, SSE plumbing. | Generic types, `shared/lib` | Domain entities, workspace or evidence types |

---

## 2. Dependency & Import Rules

`frontend/.dependency-cruiser.cjs` enforces these rules with `pnpm depcruise`:

- `no-circular` and `not-to-unresolvable` (errors).
- `no-test-imports-in-production`: production code must not import `src/test/` or `*.test|spec.ts(x)` files.
- `no-app-imports-from-lower-layers`, `no-feature-imports-from-domain-or-shared`, `no-domain-imports-from-shared`: upward imports are errors.
- `no-orphans` (warning).

Dependency Cruiser does **not** yet block feature-to-feature or domain-to-domain imports. Check those during code review. ESLint enforces the size and nesting budgets in Section 4.

1. **Unidirectional Import Flow**:
   $$\text{app} \longrightarrow \text{features} \longrightarrow \text{domains} \longrightarrow \text{shared}$$
2. **No Feature-to-Feature Coupling**:
   - If `evidence-table` must open a page in `pdf-viewer`, compose them at the `app/` level with composition slots (`children` / render props) or coordinate through a shared domain (for example, a selected-highlight value in `domains/evidence`).
3. **Domain Isolation**:
   - Domains should not cross-import. If data must be combined (for example, joining workspace trace events with evidence claims), create an app-level composition selector or pass values via typed function arguments.
4. **Public Barrel Discipline**:
   - Import external modules strictly via their top-level `index.ts` public contract.
   - **Never** import your own module through its own barrel file (prevents cyclic initialization).
5. **No Test Imports in Production**:
   - Production code must never import from `src/test/`. Fixture mode loads fixtures through a dedicated loader at the API boundary, not via direct imports from feature code.

---

## 3. Component & State Architecture

### Component Anatomy: Split by Responsibility
Avoid multi-hundred-line monolithic files. Within a feature or domain:
- **`ui/`**: Cohesive presentational components. Describes what the screen looks like.
- **`model/`**: Custom hooks (controllers), reducers, and pure calculation helpers.
- **`api/`**: Endpoint call wrappers, wire DTOs, and zod decoders.

### State Rules
1. **Narrow Domain Providers**: Avoid a single mega-context. Split state by domain (`WorkspaceContext`, `EvidenceContext`).
2. **Colocate Ephemeral State**: Keep form drafts, scope chip edits, tab selections, row expansions, and modal visibility in the local component or a feature controller hook (`useScopeBuilderController.ts`).
3. **Derive, Don't Sync**: Calculate view data during render (for example, funnel counts from screening decisions) rather than duplicating upstream state through `useEffect`.
4. **Node & Focus Identity**: When panes rearrange (for example, the PDF viewer opening beside the evidence table), preserve DOM node identity and focus state rather than unmounting and replacing elements.
5. **One Component per File**: Keep each file focused on a single named export (compound UI primitives in `shared/ui` are exempt).

---

## 4. Code Budgets & Type Safety

### Lint & Complexity Budgets (`frontend/eslint.config.js`)
`pnpm lint` runs with `--max-warnings 0`, so each warning fails the check.

- **Max File Length**: 300 lines (blank lines and comments skipped).
- **Max Function Length**: 100 lines (blank lines and comments skipped).
- **Max Cyclomatic Complexity**: $\le 12$.
- **Max Nesting Depth**: $\le 4$ levels.
- **Max Nested Callbacks**: $\le 3$.
- **Max Function Parameters**: $\le 4$ parameters (use option objects for more).
- **No `any`**: `@typescript-eslint/no-explicit-any` is an error.
- Test files (`*.test|spec.ts(x)`) are exempt from the size, complexity, callback, and parameter budgets.

### Strict Typing Guidelines
- **External Data is Unknown**: Treat incoming API payloads and SSE events as `unknown`; decode them with zod in `domains/*/api` before they reach view models.
- **Guard Array Access**: Always guard index lookups (`const item = list[i]; if (!item) return;`).
- **Discriminated Unions**: Model mutually exclusive states (async status `idle | loading | success | error`, trace event `kind`, research mode `medical | general`) with tagged unions to eliminate illegal state combinations.
- **No Blanket `any`**: Use `satisfies` and explicit mock types; avoid type assertions (`as SomeType`) without verification.

---

## 5. Hackathon Test Policy

These rules apply until the hackathon ends. They override broader test guidance in the other frontend skills.

1. **Vitest only for edge cases** in:
   - wire decoders (malformed or missing fields),
   - the SSE event reducer (out-of-order, duplicate, resume),
   - pure helpers with boundaries.
2. **No** component snapshot tests, **no** layout or styling tests, **no** coverage targets.
3. **At most one browser smoke test** for the demo path. Add it in Phase 3 of `PLAN.md` with plain `@playwright/test` against fixture mode (`VITE_USE_FIXTURES=1`). Playwright is not installed until then.
4. **Run `pnpm test` only when test files exist.** Do not add artificial tests to avoid an empty suite; keep empty-suite failures visible.

---

## 6. Test Organization & Preservation

1. **Colocated Unit Tests**:
   - Place Vitest tests directly alongside the implementation (`workspaceEventReducer.ts` $\rightarrow$ `workspaceEventReducer.test.ts`).
   - Keep shared helpers, setup, and recorded fixtures in `frontend/src/test/`.
2. **Robust Semantic Selectors** (when a component test is justified):
   - Query by user-facing roles and accessibility labels (`getByRole("button", { name: /start run/i })`, `getByLabelText`).
   - Avoid brittle DOM structure queries (e.g., `container.querySelector("div.grid > div.border")`).
3. **Browser Smoke Test**:
   - The single Phase 3 Playwright smoke test covers the demo path against fixture mode. Gherkin/BDD is deferred (see `frontend-bdd-test-skill`).
4. **Characterization Before Refactoring**:
   - Before you refactor a complex flow (for example, SSE resume or GRADE row mapping), write a characterization test that locks in current behavior.

---

## 7. Pre-Commit Verification Checklist

Before you open a PR or complete a frontend slice, run these commands from `frontend/`:

- [ ] New components placed in the appropriate `features/`, `domains/`, or `shared/` layer.
- [ ] No direct feature-to-feature or illegal upward imports.
- [ ] Reusable UI components in `shared/ui` contain zero business logic or domain types.
- [ ] File and function lengths meet ESLint budgets ($\le 300$ file lines, $\le 100$ function lines, $\le 12$ complexity).
- [ ] Audit pipeline passes completely:
  ```powershell
  pnpm check   # format:check + depcruise + knip + lint + typecheck
  pnpm build
  pnpm test    # only when test files exist
  ```
