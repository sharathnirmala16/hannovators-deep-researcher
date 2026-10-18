---
name: backend-code-quality
description: "Review code quality, audit changes, enforce import hygiene, check cyclomatic complexity, catch unused code, and run static type checking with Ruff and MyPy. Use when you format code, verify type safety, audit before PR submission, or fix lint and type errors across src/hannovators_deep_researcher and tests/."
---

# Code Quality & Static Analysis with Ruff & MyPy

Automated code quality auditing, import boundary verification, unused-code detection, cyclomatic complexity checks, and strict type safety verification.

Installed tooling (dev group in `pyproject.toml`): Ruff, MyPy, pytest, pytest-asyncio, behave. `respx` is added in Phase 0 of PLAN.md. Tools such as vulture, radon, import-linter, or mutation testing are **not installed** and are not gates; treat them as optional extras only.

## 1. Execution Path: Choose the Lightest Path

**Audit Pipeline**: `uv run ruff format --check ──> uv run ruff check ──> uv run mypy ──> uv run pytest -m "not live" ──> uv build`

* **Inner Loop (Active Development / Single File)**:
  ```bash
  uv run ruff format src/hannovators_deep_researcher/services/provider_router.py && uv run ruff check src/hannovators_deep_researcher/services/provider_router.py
  ```
* **Fast Typecheck**:
  ```bash
  uv run mypy
  ```
* **Auto-Fix Safe Lint & Format Issues**:
  ```bash
  uv run ruff check --fix && uv run ruff format
  ```
* **Outer Loop (Pre-PR / Full Audit)**:
  ```powershell
  uv run ruff format --check ; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  uv run ruff check ; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  uv run mypy ; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  uv run pytest -m "not live" ; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  uv build ; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  ```
* **Live provider checks (optional, needs API keys)**: `uv run pytest -m live`

Which tests to write at all is governed by the **Hackathon Test Policy** in `.agents/skills/backend-code-structure/SKILL.md` (section 4).

---

## 2. Core Guardrails & Rule Sets

| Rule Set | Code | Threshold / Rule | Scope |
| :--- | :--- | :--- | :--- |
| **Cyclomatic Complexity** | `C901` | McCabe Complexity $\le 15$ | `src/` (exempt in `tests/**`) |
| **Line Length** | `E501` | $\le 100$ characters | Workspace-wide |
| **Strict Type Safety** | MyPy | `strict = true`, no untyped defs, explicit `T \| None` | `src` and `tests` (`hannovators_deep_researcher`) |
| **Unused Items** | `F401`, `F841` | 0 unused imports or variables | Workspace-wide |
| **Code Simplification** | `SIM`, `B` | Simplify nested conditionals, avoid bug patterns | Workspace-wide |
| **Modern Python 3.12+** | `UP` | Enforce `X \| Y` unions, built-in generic collections (`list[str]`) | Workspace-wide |
| **Import Hygiene** | `I`, `TID` | Deterministic isort ordering, clean boundaries | Workspace-wide |

Correct violations instead of adding broad rule exceptions.

---

## 3. Troubleshoot Predictably

| Symptom | Cause | Action |
| :--- | :--- | :--- |
| **`C901 ... is too complex (X > 15)`** | Function has too many branches/loops | Extract nested helper functions or replace `if/elif` chains with dictionary dispatch tables. |
| **`RUF023 __slots__ is not sorted`** | `__slots__` tuple elements are out of alphabetical order | Sort tuple items alphabetically: `__slots__ = ("a", "b")`. |
| **`Incompatible return value type`** | Missing explicit `None` handling in union | Use `T \| None` return annotation and guard with `if result is None:` before returning. |
| **`Function is missing a type annotation`** | Untyped parameter or return under strict MyPy | Add explicit type annotations to all parameters and return types (`def f(x: int) -> str:`). |
| **`F401 ... imported but unused`** | Leftover or unreferenced import | Remove unused import or add `# noqa: F401` if required for re-export in `__init__.py`. |
| **`Untyped import error (import-untyped)`** | 3rd-party dependency lacks py.typed marker | Add `# type: ignore[import-untyped]` on the specific import line. |
| **`'live' not found in markers`** | `--strict-markers` and marker not registered | Register `live`/`e2e` in `[tool.pytest.ini_options] markers` (Phase 0 of PLAN.md). |

---

## 4. Checklist

- [ ] `uv run ruff format --check` exits with all files formatted.
- [ ] `uv run ruff check` exits with 0 lint, unused-code, or complexity errors.
- [ ] `uv run mypy` exits with 0 type errors across `src` and `tests`.
- [ ] `uv run pytest -m "not live"` passes (empty-suite failures stay visible).
- [ ] `uv build` succeeds.
