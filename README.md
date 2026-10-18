# Hannovators Deep Researcher

This repository contains Python, SQLite, and React boilerplate. It has no product features or backend server.

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

The frontend displays a blank application shell with Tailwind and shadcn support.

`pnpm dev` reads `VITE_PORT` and `API_PORT` from the root `.env`. A shell variable overrides the `.env` value.
The dev server uses `VITE_PORT` and stops if that port is not available.
It sends `/api` and `/files` requests to the backend at `http://127.0.0.1:<API_PORT>`.
If a port is missing or not correct, `pnpm dev` stops and shows the name of the variable.
`pnpm build` and `pnpm test` do not use the ports.

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

Python tests check the database infrastructure and migrations. Use `pnpm test` from `frontend/` for Vitest tests.
The frontend has no tests. Vitest reports an empty suite and returns a nonzero exit code until real tests exist.
Do not add artificial tests or suppress empty suites. This project has no GitHub CI.
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
The initial revision contains no product tables.

Reserve `data/seeds/<UUID>/` for each seed material. Use a new UUID as the material's unique directory identifier.
This scaffold defines the directory convention only. It contains no seed ingestion or product schema.
See [PLAN.md](PLAN.md) for the planned schema and the `data/workspaces/` layout that replaces `data/seeds/`.

## UI components

Tailwind uses the Vite plugin and `frontend/src/index.css`. The CSS file defines shadcn theme tokens.
The `@/` alias points to `frontend/src/`. The shadcn configuration places UI components in `src/shared/ui/`.

`src/shared/ui/` contains these shadcn primitives: badge, button, card, dialog, input, progress, resizable, scroll-area, separator, sonner, table, tabs, textarea, and tooltip.
The primitives use the `cn` package for class names. Dialog and tooltip animations use `tw-animate-css`.
The frontend also includes `zod` for wire decoders and `cytoscape` for the citation graph.

Feature lanes must not change `frontend/package.json` or `frontend/pnpm-lock.yaml`.
To add a primitive, use the shadcn CLI version that made the current primitives:

```sh
pnpm dlx shadcn@4.21.4 add <component>
```

Use `pnpm format` to apply the frontend format rules.
