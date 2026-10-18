# Project guide

- Keep changes within scope. Use `.archive/freesearch/` as a reference only.
- Use `uv` and `pnpm`. Update lockfiles with dependency changes. Do not add GitHub CI.
- Read `PLAN.md` sections 1 to 6, then your lane card. Edit only the files your lane owns. Do not edit frozen `[P0]` files, lockfiles, or migrations in a lane.

## Structure

- Python: `src/hannovators_deep_researcher/`. Use role packages and absolute imports. Keep transport handlers thin and package initializers small.
- Mirror Python packages under `tests/unit/` and `tests/integration/`. Put end-to-end tests in `tests/e2e/` and provider live checks in `tests/live/`.
- React: `frontend/src/`. Follow `app -> features -> domains -> shared`. Do not import one feature from another.
- Colocate frontend tests as `*.test.ts(x)`. Keep shared helpers in `frontend/src/test/`.
- Use Tailwind and shadcn. Put UI primitives in `frontend/src/shared/ui/`.
- Keep SQLite and workspace files under root `data/`. Use `data/workspaces/<workspace_id>/sources/<source_id>/` for source files.
- Use Alembic revisions for schema changes. Keep runtime data out of Git.
- Read relevant `.agents/skills/` instructions.

## Tests

- Do not write new unit tests or rerun the suite while you build. Run all checks once at the end of your work and fix what fails. Keep existing tests green; update them when a contract change breaks them.
- New tests are limited to a few live end-to-end tests of critical functions (`tests/e2e/test_live_*.py`, markers `live` and `e2e`), written after the features work.
- Do not test trivial happy paths, DTOs, wiring, layout, or styling. No snapshot tests. No coverage targets.
- Mark tests `unit`, `integration`, `live`, or `e2e`. Live checks skip when an API key is missing and make one small request each.
- Mock HTTP with `respx` at the adapter boundary. Use the fakes in `adapters/fake/` for service and end-to-end tests.
- Behave and Playwright-BDD are deferred. Phase 3 adds one plain Playwright smoke test.

## Worktrees and ports

Each worktree has fixed, isolated ports in its root `.env` so agents can run servers at the same time.

| Workspace | Directory | Backend API (`API_PORT`) | UI dev (`VITE_PORT`) |
| :--- | :--- | :--- | :--- |
| Main | `hannovators-deep-researcher` | `8001` | `5174` |
| WT 1 | `hdr_wt_1` | `8011` | `5175` |
| WT 2 | `hdr_wt_2` | `8021` | `5176` |
| WT 3 | `hdr_wt_3` | `8031` | `5177` |
| WT 4 | `hdr_wt_4` | `8041` | `5178` |
| WT N (up to 9) | `hdr_wt_N` | `8001 + 10 * N` | `5174 + N` |

- Create a worktree from the main repository root: `scripts\windows\create_worktree.bat <branch> <slot> [full|backend|frontend|bare]`. It writes the slot ports into the worktree `.env`, runs `uv sync --locked`, `uv run alembic upgrade head`, and `pnpm install --frozen-lockfile`.
- Delete it: `scripts\windows\delete_worktree.bat <slot|branch> [--force] [--keep-branch]`.
- Each worktree has its own `.env`, `.venv`, `node_modules`, and `data/hannovators.db`.
- Launch servers without port flags. They read the local `.env` and stop when a port is missing.
- Keep ports out of committed files.

## Checks

- From the root: `uv run ruff format --check`, `uv run ruff check`, `uv run mypy`, and `uv build`.
- From `frontend/`: `pnpm check` and `pnpm build`.
- At the end of your work, run `uv run pytest` (skips `live`) and `pnpm test`. Run `uv run pytest -m live` only when you changed an adapter or a live e2e test.
- Keep strict types and complexity limits. Correct violations instead of broad rule exceptions.
- Update the README when commands or structure change.

<!-- BACKLOG.MD GUIDELINES START -->
<!-- backlog.md-instructions-version: 1.53.0 -->
<CRITICAL_INSTRUCTION>

## Backlog.md Workflow

This project uses Backlog.md for task and project management.

**At the beginning of each conversation in this project, run `backlog instructions overview` before answering or taking action. Re-read it only if you have not read it yet in the current conversation.**

Use the overview to decide whether to search, read, create, or update Backlog tasks.

Before task lifecycle actions, read the matching detailed guide:
- `backlog instructions task-creation` before creating or splitting tasks
- `backlog instructions task-execution` before planning, changing status or assignee, adding a plan or implementation notes, or implementing task work
- `backlog instructions task-finalization` before checking acceptance criteria, writing final summaries, or moving tasks to terminal statuses

Use `backlog <command> --help` before running unfamiliar commands. Help shows options, fields, and examples.

Do not edit Backlog task, draft, document, decision, or milestone markdown files directly. Use the `backlog` CLI so metadata, relationships, and history stay consistent.

</CRITICAL_INSTRUCTION>
<!-- BACKLOG.MD GUIDELINES END -->
