---
name: backend-code-structure
description: "Guidelines and conventions for backend module boundaries, package responsibilities, import hygiene, mirrored unit/integration test layouts, and the hackathon test policy for src/hannovators_deep_researcher. Use when creating new modules, refactoring backend code, structuring tests, or auditing package boundaries."
---

# Backend Code Structure & Architecture Guidelines

A clean, modular architecture enforcing single responsibility per package, unidirectional dependencies, clean import boundaries, and a mirrored test layout.

---

## 1. Package Responsibilities (`src/hannovators_deep_researcher/`)

Modules are strictly organized by operational role and dependency layering:

| Package | Purpose & Ownership | Constraints & Rules |
| :--- | :--- | :--- |
| **`models/`** | Domain contracts, DTOs, schemas, enums, validation, and ports (`models/ports.py`: `typing.Protocol` interfaces for LLM, embeddings, decision API, web search, PubMed). | Pure data structures and interfaces. Use Pydantic explicitly for each contract. Do not import transport, database, or vendor SDK modules. |
| **`configuration/`** | Settings models, environment variable loaders, provider configs, registries. | Exposes cached/singleton accessors. No operational business logic. |
| **`services/`** | Core business logic, provider routing, orchestration, and the deep-research pipeline (`services/pipeline/stages/<stage>/` packages). | Distinct from HTTP routers. Depends on models, persistence, and adapters via ports. |
| **`adapters/`** | External integrations implementing ports (Nebius Token Factory LLM/embeddings, Jev System One, Tavily and other web search providers, PubMed). Offline fakes live in `adapters/fake/`. | Encapsulates vendor-specific HTTP/SDK calls and error mapping into domain contracts. |
| **`infrastructure/`** | Cross-cutting technical plumbing (HTTP clients, logging, resilience/retries). | Reusable technical utilities; independent of domain business rules. |
| **`persistence/`** | SQLite repositories, SQLAlchemy tables, migration runners, and Alembic version scripts. | Owns schema definitions and raw queries. Returns domain models or entity aggregates. |
| **`routers/`** | FastAPI transport-layer endpoints. | Thin handlers: validate request parameters, call services, and return responses. No inline DB queries. |

The composition root is `src/hannovators_deep_researcher/main.py`: it builds the FastAPI app and wires concrete (or fake) adapters into services. No other module should assemble the object graph.

There is no `mcp/` or `cli/` package yet. If one is added later, treat it as another transport layer alongside `routers/`.

Use Pydantic for domain contracts in `models/` (e.g. `models/contracts.py`). Each new domain contract must use Pydantic explicitly.

---

## 2. Dependency Flow & Import Hygiene

### Unidirectional Dependency Flow

```
[ routers/ ] (Transport Layer)        main.py (composition root)
        │
        ▼
   [ services/ ] (Domain Logic, Pipeline & Orchestration)
   ┌────┼──────────────┐
   ▼    ▼              ▼
[ adapters/ ]  [ persistence/ ]  [ infrastructure/ ]
   │    │              │                │
   └────┴───────┬──────┴────────────────┘
                ▼
      [ models/ & configuration/ ] (Foundations)
```

1. **Strict Layering**: Upper layers may import from lower layers; lower layers must never import from upper layers. Never import from `routers/` or `main.py` inside `services/`, `adapters/`, or `persistence/`. Services depend on ports in `models/ports.py`, not on concrete adapter classes.
2. **Package Import Paths**: Use explicit, absolute package imports (e.g., `from hannovators_deep_researcher.models.contracts import ResearchRequest`). Avoid relative imports spanning across package boundaries (`../../`).
3. **Clean `__init__.py` Markers**: Keep package initializers lean. Avoid eager cascading imports that cause circular dependency chains.
4. **Circular Dependency Handling**:
   - Prefer extracting shared contracts to `models/` or using dependency injection.
   - If runtime composition demands a mutual reference, keep the import **localized inside the calling function or method**, never at module level.

---

## 3. Test Structure & Classification

Mirror the source tree under `tests/` split strictly by execution speed and runtime boundaries:

```text
tests/
  conftest.py                     # Root shared fixtures and test configuration
  fixtures/                       # Static mock payloads and JSON fixtures
  unit/                           # Fast, isolated tests with zero live I/O
    adapters/                     # Mirrors src/hannovators_deep_researcher/adapters/
    configuration/                # Mirrors src/hannovators_deep_researcher/configuration/
    infrastructure/               # Mirrors src/hannovators_deep_researcher/infrastructure/
    models/                       # Mirrors src/hannovators_deep_researcher/models/
    services/                     # Mirrors src/hannovators_deep_researcher/services/
  integration/                    # Tests touching real SQLite, migrations, or the HTTP app
    routers/                      # FastAPI endpoint workflows (incl. `e2e` pipeline tests)
    persistence/                  # SQLite repositories and Alembic migrations
    services/                     # Services exercising real persistence
    adapters/                     # `live` provider checks (real network + API keys)
  bdd/
    features/                     # Gherkin scenarios (Behave deferred for the hackathon)
```

### Classification Criteria
- **Unit (`tests/unit/`)**: Fast and fully isolated. External HTTP is mocked with `respx`; ports are satisfied with fakes from `adapters/fake/`.
- **Integration (`tests/integration/`)**: Uses a real SQLite database, executes Alembic migrations, runs the FastAPI app end to end, or hits a live provider. If any test in a module touches real integration boundaries, classify the module under `integration/`.
- **Mirroring Convention**: Name test files after the module they test (`src/hannovators_deep_researcher/services/provider_router.py` $\rightarrow$ `tests/unit/services/test_provider_router.py`).

---

## 4. Hackathon Test Policy

Write tests only for:
- **(a) Edge cases in pure logic**: boundaries, empty inputs, malformed external payloads, provider failover, path safety.
- **(b) One cheap live check per external provider.**
- **(c) A few end-to-end tests of the critical pipeline path.**

Rules:
- Do not write tests for trivial happy paths, simple DTOs, getters, or wiring. No snapshot tests. No coverage targets.
- **Markers**: `unit`, `integration`, `live` (real network + API keys; skip when the key is missing), `e2e` (full pipeline through the HTTP API).
  - Default run: `uv run pytest -m "not live"`.
  - Live checks: `uv run pytest -m live`.
  - Phase 0 of PLAN.md registers the `live` and `e2e` markers in `pyproject.toml` (`--strict-markers` is on).
- Mock HTTP at the adapter boundary with `respx`; use the fake adapters in `adapters/fake/` for ports in service and e2e tests.
- Live tests make one small request each: low limits, no loops, no retries beyond the adapter default.
- Each lane in PLAN.md lists its required edge-case tests; do not add more without a reason.

---

## 5. Mocking & Path Seams

- **Mock at the Consumer Lookup Site**: Always patch symbols where they are *imported and used*, not where they are defined.
  - *Correct*: `patch("hannovators_deep_researcher.routers.research.build_pipeline")`
  - *Incorrect*: `patch("hannovators_deep_researcher.services.pipeline.factory.build_pipeline")` (the definition site)
- Prefer injecting fakes from `adapters/fake/` through the composition root over `patch` where possible.
- **Stable Path Resolution**: Never calculate file paths using brittle relative levels. Always anchor using `Path(__file__).resolve().parents[N]` matched to directory depth, or use `Path.cwd()` when resolving workspace paths (e.g. root `data/`).

---

## 6. Pre-Commit Verification Checklist

When adding new modules, moving code, or updating package boundaries, run:

- [ ] New source modules placed in the appropriate `src/hannovators_deep_researcher/<package>/` subpackage.
- [ ] Any new subpackage includes an `__init__.py` file.
- [ ] No circular imports introduced at module scope.
- [ ] Unit tests placed in `tests/unit/<package>/` mirroring source layout.
- [ ] Tests touching DB/migrations, the HTTP app, or live providers placed in `tests/integration/<package>/`.
- [ ] New tests justified by the Hackathon Test Policy (section 4).
- [ ] Mock patches target consumer lookup sites.
- [ ] Verification suite passes:
  ```powershell
  uv run ruff format --check
  uv run ruff check
  uv run mypy
  uv run pytest -m "not live"
  uv build
  ```
