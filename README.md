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

From `frontend/`, add a component when the product needs it:

```sh
pnpm dlx shadcn@latest add button
```

The scaffold contains no example UI components. Use `pnpm format` to apply the frontend format rules.
