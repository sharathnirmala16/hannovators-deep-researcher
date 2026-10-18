# Project guide

- Keep changes within scope. Use `.archive/freesearch/` as a reference only.
- Use `uv` and `pnpm`. Update lockfiles with dependency changes. Do not add GitHub CI.

## Structure

- Python: `src/hannovators_deep_researcher/`. Use role packages and absolute imports. Keep transport handlers thin and package initializers small.
- Mirror Python packages under `tests/unit/` and `tests/integration/`. Put Gherkin scenarios in `tests/bdd/features/`.
- React: `frontend/src/`. Follow `app -> features -> domains -> shared`. Do not import one feature from another.
- Colocate frontend tests as `*.test.ts(x)`. Keep shared helpers in `frontend/src/test/`.
- Use Tailwind and shadcn. Put UI primitives in `frontend/src/shared/ui/`.
- Keep SQLite and seed material under root `data/`. Use `data/seeds/<UUID>/` for each material.
- Use Alembic revisions for schema changes. Keep runtime data out of Git.
- Read relevant `.agents/skills/` instructions. Adapt legacy `freesearch` paths to this project.

## Checks

- From the root: `uv run ruff format --check`, `uv run ruff check`, `uv run mypy`, and `uv build`.
- From `frontend/`: `pnpm check` and `pnpm build`.
- Run `uv run pytest`. Run `pnpm test` when frontend tests exist. Keep empty-suite failures visible.
- Keep strict types and complexity limits. Correct violations instead of broad rule exceptions.
- Update the README when commands or structure change.
