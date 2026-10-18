---
name: frontend-code-quality
description: "Audit architecture boundaries, circular imports, dead code, unused exports, cyclomatic complexity, nesting depth, formatting, and TypeScript type safety in frontend/src. Use when you verify PR readiness, review code changes, diagnose dependency-cruiser violations, fix ESLint complexity errors, or resolve Knip unused export and dependency reports."
---

# Code Quality & Static Analysis

Enforces architectural boundaries, dead-code elimination, cyclomatic complexity limits, formatting, and TypeScript type safety across `frontend/src`.

For which tests to write, follow the **Hackathon Test Policy** in `frontend-code-structure` (Section 5).

## 1. Audit Pipeline

**Workflow**: `pnpm format:check` ──> `pnpm depcruise` ──> `pnpm knip` ──> `pnpm lint` ──> `pnpm typecheck`

`pnpm check` runs the full pipeline in that order. Run it from `frontend/`:

```powershell
pnpm check
pnpm build
pnpm test    # only when test files exist
```

Run single steps when you iterate:

```powershell
pnpm format       # apply Prettier fixes
pnpm depcruise
pnpm knip
pnpm lint
pnpm typecheck
```

---

## 2. Tools & Rule Matrix

| Tool | Focus Area | Inner-Loop / Targeted Check | Full Command | Config File |
| :--- | :--- | :--- | :--- | :--- |
| **Prettier** | Formatting | `pnpm exec prettier --check <target-file>` | `pnpm format:check` | `.prettierrc.json` |
| **Dependency Cruiser** | Cycles, resolvable paths, layer direction, test imports | `pnpm depcruise` | `pnpm depcruise` | `.dependency-cruiser.cjs` |
| **Knip** | Dead code, unused exports/deps | `pnpm knip` | `pnpm knip` | `knip.json` |
| **ESLint** | Complexity (≤12), nesting, size budgets, hooks | `pnpm exec eslint <target-file>` | `pnpm lint` | `eslint.config.js` |
| **TypeScript** | Strict compile-time type verification | `pnpm exec tsc -b --pretty false` | `pnpm typecheck` | `tsconfig.json` (refs `tsconfig.app.json`, `tsconfig.node.json`, `tsconfig.test.json`) |

---

## 3. Core Boundary Rules & Budgets

`.dependency-cruiser.cjs` declares these rules:

* **`no-circular`** (error): Zero circular dependencies. A cycle causes runtime init faults and broken HMR.
* **`not-to-unresolvable`** (error): Every import must resolve. This rule catches broken paths and absent packages.
* **`no-test-imports-in-production`** (error): Production code must not import `src/test/` or test files.
* **`no-app-imports-from-lower-layers`**, **`no-feature-imports-from-domain-or-shared`**, **`no-domain-imports-from-shared`** (errors): Enforce `app -> features -> domains -> shared`.
* **`no-orphans`** (warning): Flags each file that no other file imports.

Feature-to-feature (for example, `features/evidence-table` importing `features/pdf-viewer`) and domain-to-domain imports are not tool-enforced. Check them in review.

**ESLint budgets** (`eslint.config.js`, `--max-warnings 0`): max 300 lines per file, max 100 lines per function, complexity ≤ 12, max depth 4, max nested callbacks 3, max params 4, no explicit `any`. Test files are exempt from the size, complexity, callback, and parameter budgets.

---

## 4. Troubleshoot Predictably

| Symptom | Cause | Action |
| :--- | :--- | :--- |
| **`not-to-unresolvable` error** | An import path is broken or a package is absent | Correct the import path or install the package with `pnpm add`. |
| **`no-circular` error** | Two files import each other's types/values | Extract shared types or utility functions into a dedicated sub-module. |
| **Layer rule error** | A lower layer imports a higher one (e.g., `domains/workspace` importing `features/workbench-shell`) | Move the shared value down a layer or pass it in from `app/`. |
| **Knip flags a file or export** | Code is unreferenced, or a generated/fixture file falls inside `project` globs | Remove dead code. Keep generated output outside `src/`; load fixtures through a referenced loader. |
| **ESLint complexity warning (>12)** | Deep branching with multiple `if/else`, `switch`, or `&&/\|\|` | Replace compound conditionals with lookup tables, discriminated-union handlers, or helper extraction. |
| **`format:check` fails** | Unformatted files | Run `pnpm format` and review the diff. |

---

## 5. Review Checklist

- [ ] `pnpm check` exits 0 (format, depcruise, knip, lint, typecheck).
- [ ] `pnpm build` exits 0.
- [ ] `pnpm test` exits 0 when test files exist.
- [ ] No feature-to-feature or domain-to-domain imports in the diff.
