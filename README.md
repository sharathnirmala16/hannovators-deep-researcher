# Hannovators Deep Researcher

An adaptive deep-research and evidence-synthesis workbench. Ask a research question, optionally add seed papers
(PDF, PMID, DOI, or URL), and the pipeline searches PubMed and the web, screens and appraises the sources, and writes a
GRADE-style synthesis. Every finding, synthesis citation, and chat answer links to the exact highlighted passage in its
source PDF. The Trajectory tab records every model call, search, download, decision, and user action of a run.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 24. The `.node-version` file specifies the local version.
Use the pnpm version in `frontend/package.json`. Corepack can select this version with `corepack pnpm`.

From the repository root:

```sh
uv sync --locked
```

From `frontend/`:

```sh
pnpm install --frozen-lockfile
pnpm dev
```

Open `http://localhost:<VITE_PORT>` (with the API running, see Run). The workspaces page starts a new run or reopens one.

`pnpm dev` reads `VITE_PORT` and `API_PORT` from the root `.env`. A shell variable overrides the `.env` value.
The dev server uses `VITE_PORT` and stops if that port is not available.
It sends `/api` and `/files` requests to the backend at `http://127.0.0.1:<API_PORT>`.
If a port is missing or not correct, `pnpm dev` stops and shows the name of the variable.
`pnpm build` and `pnpm test` do not use the ports.

## Run

From the repository root, migrate the database once, then start the API:

```sh
uv run alembic upgrade head
uv run hdr-api
```

`hdr-api` serves on `API_HOST` and `API_PORT` from the root `.env`. `--host` and `--port` override them.
If no port is set, it stops with an error. There is no default port.

Set `PROVIDER_MODE=fake` in `.env` or the shell to run offline with the fakes in `adapters/fake/` for every port.
With `PROVIDER_MODE=real`, each port uses its real adapter when the adapter exists and its key is set.
Otherwise that port uses its fake and the server logs a warning.
`GET /api/health/providers` shows which ports are real or fake and which keys are configured. It never shows key values.

The API is under `/api` (PLAN.md section 5.2). `GET /api/workspaces/{id}/events` is the SSE trace stream.
Source files are served from `data/workspaces/` at `/files/workspaces/`.

## Structure

- `src/hannovators_deep_researcher/`: Python packages for models, configuration, services, adapters, infrastructure, persistence, and routers.
- `tests/`: separate unit, integration, and BDD directories.
- `frontend/src/`: application composition, features, domains, shared primitives, and test helpers.
- `data/`: local SQLite database and seed material. Git excludes runtime files.
- `.agents/skills/`: local architecture, quality, and test conventions.
- `.archive/`: reference projects. Normal build and quality checks exclude these files.

## Checks

From the repository root:

```sh
uv run ruff format --check
uv run ruff check
uv run mypy
uv run pytest
uv build
```

From `frontend/`:

```sh
pnpm check
pnpm build
```

These commands check format, lint rules, strict types, dependencies, and package builds.

Plain `uv run pytest` deselects tests marked `live`. Run `uv run pytest -m "e2e and not live"` for the offline
end-to-end tests (fake providers). Run `uv run pytest -m live` for the provider checks and the live end-to-end tests
in `tests/e2e/test_live_*.py` (platform, grounding, research quality). Each one skips when its API key is missing; the
grounding test also needs the seed PDFs in `../data/seed_1` (or `SEED_PDF_DIR`). Live runs take minutes and cost a
little provider credit. Use `pnpm test` from `frontend/` for Vitest tests. Do not add artificial tests or suppress
empty suites. This project has no GitHub CI.
BDD directories reserve space for future scenarios. Add the browser test tools with the first browser workflow.

## Worktrees

Parallel agents work in separate Git worktrees. From the repository root on Windows:

```bat
scripts\windows\create_worktree.bat <branch> <slot 1-9> [full|backend|frontend|bare]
scripts\windows\delete_worktree.bat <slot|branch> [--force] [--keep-branch]
```

The create script makes `..\hdr_wt_<slot>`, copies `.env` with the slot ports, installs the backend and the frontend, and migrates the worktree database.
AGENTS.md lists the port for each slot. Copy `.env.example` to `.env` in the main repository first and set `API_PORT=8001` and `VITE_PORT=5174`.

## Database and seed material

The default SQLite database is `data/hannovators.db`. The database path stays at the repository root when the process directory changes.
Copy `.env.example` to `.env` for local overrides.

From the repository root:

```sh
uv run alembic upgrade head
uv run alembic current
```

Create each schema change with `uv run alembic revision --autogenerate -m "describe change"`.
Review the revision before you run `uv run alembic upgrade head`.
Revisions `0002` and `0003` hold the product schema.

Source files live in `data/workspaces/<workspace_id>/sources/<source_id>/` (`raw.pdf`, `snapshot.md`,
`highlighted.pdf`). See [PLAN.md](PLAN.md) section 4 for the schema.

## UI components

The visual system ("annotated paper") is specified in PLAN.md section 10.3: solid hex color tokens only (the IDE preview
browser renders opacity modifiers, `color-mix()`, and 8-digit hex wrongly), Atkinson Hyperlegible Next and Mono, and
Literata for reading text. The fonts come from `@fontsource-variable` packages, so the app works offline. The PDF viewer
uses `pdfjs-dist`.

Tailwind uses the Vite plugin and `frontend/src/index.css`. The CSS file defines shadcn theme tokens.
The `@/` alias points to `frontend/src/`. The shadcn configuration places UI components in `src/shared/ui/`.

`src/shared/ui/` contains these shadcn primitives: badge, button, card, dialog, input, progress, resizable, scroll-area, separator, sonner, table, tabs, textarea, and tooltip.
The primitives use the `cn` package for class names. Dialog and tooltip animations use `tw-animate-css`.
The frontend also includes `zod` for wire decoders and `react-force-graph-2d` with `d3-force` for the citation graph.

Feature lanes must not change `frontend/package.json` or `frontend/pnpm-lock.yaml`.
To add a primitive, use the shadcn CLI version that made the current primitives:

```sh
pnpm dlx shadcn@4.21.4 add <component>
```

Use `pnpm format` to apply the frontend format rules.
