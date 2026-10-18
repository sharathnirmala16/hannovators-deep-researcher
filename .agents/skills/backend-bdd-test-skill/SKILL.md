---
name: backend-bdd-test-skill
description: "DEFERRED for the hackathon (use pytest e2e tests instead); reference for after the hackathon. Author, maintain, and execute Behavior-Driven Development (BDD) tests in Python using Behave and Gherkin feature files. Use when adding acceptance scenarios, writing typed step definitions, using Scenario Outlines and DataTables, managing environment.py async lifecycle hooks, generating step skeletons, or diagnosing Behave test failures."
---

# Behave (Cucumber) BDD Skill for Python

> **Status: deferred for the hackathon.** Do not add Behave scenarios now. Cover the critical pipeline path with pytest `e2e` tests instead (see the **Hackathon Test Policy** in `.agents/skills/backend-code-structure/SKILL.md`, section 4). Keep this skill as reference for after the hackathon.

Systematic Behavior-Driven Development (BDD) testing in Python using **Behave** (`behave`) and **Gherkin (`.feature`) files**.

## 1. Execution Path: Choose the Lightest Path

**Workflow**: `Write .feature ──> uv run behave --dry-run (skeletons) ──> Implement tests/bdd/features/steps/*.py ──> uv run behave`

* **Inner Loop (Active Development / Single Scenario)**:
  ```bash
  uv run behave tests/bdd/features/provider_routing.feature   # Run specific feature file
  uv run behave tests/bdd/features/research_pipeline.feature  # Run another feature file
  uv run behave --tags=@smoke                                 # Run specific tag
  ```
* **Step Skeleton Discovery (Code Generation)**:
  ```bash
  uv run behave --dry-run                        # Prints missing @given/@when/@then snippets
  ```
* **Live Run with Console Output**:
  ```bash
  uv run behave --no-capture                     # Disables stdout/stderr capture during execution
  ```
* **Outer Loop (Full Suite & Reporting)**:
  ```bash
  uv run behave --junit --junit-directory=reports/behave/
  ```

---

## 2. Directory Structure & File Conventions

```
tests/bdd/features/
├── environment.py                  # Global & scenario lifecycle hooks (setup/teardown)
├── provider_routing.feature        # Declarative Gherkin feature specifications
├── research_pipeline.feature
└── steps/                          # Python step definitions
    ├── provider_routing_steps.py   # @given, @when, @then step implementations
    └── research_pipeline_steps.py
```

`pyproject.toml` sets `[tool.behave] paths = ["tests/bdd/features"]`. Do not place feature files in a root `features/` directory.

---

## 3. Gherkin Feature Design Patterns

### 1. Basic Scenario with Typed Parameters
```gherkin
Feature: Provider Routing & Fallbacks
  As a research pipeline
  I want web search queries routed to healthy providers
  So that research runs survive a provider outage

  Background:
    Given an "auto" web search provider router

  @smoke
  Scenario: Route query to primary provider
    When I submit a search request for "CRISPR off-target effects" with limit 5
    Then the active provider should be "tavily"
    And the returned result count should be 5
```

### 2. Scenario Outlines with Parameter Matrices
```gherkin
  Scenario Outline: Failover when the primary provider fails
    Given provider "<failing>" returns an error
    When I submit a search request for "<query>" with limit 3
    Then the active provider should be "<fallback>"

    Examples:
      | failing | query               | fallback |
      | tavily  | mRNA vaccine safety | exa      |
      | exa     | mRNA vaccine safety | tavily   |
```

### 3. DataTables & Multiline DocStrings
```gherkin
  Scenario: Batch provider configuration
    Given the following provider registry:
      | provider | priority | enabled |
      | tavily   | 1        | true    |
      | exa      | 2        | true    |
      | brave    | 3        | false   |
    When I initialize the "auto" provider router
    Then only 2 providers should be active
```

---

## 4. Step Implementations & Async Handling

### Typed Step Matchers (`tests/bdd/features/steps/*.py`)
Behave supports parse formatters: `{name}` (str), `{limit:d}` (int), `{cost:f}` (float), `{word:w}` (single word).

```python
from typing import Any

from behave import given, then, when  # type: ignore[import-untyped]

from hannovators_deep_researcher.adapters.fake import build_fake_search_providers
from hannovators_deep_researcher.services.provider_router import AutoSearchRouter


@given('an "auto" web search provider router')
def step_given_router(context: Any) -> None:
    context.router = AutoSearchRouter(build_fake_search_providers())


@when('I submit a search request for "{query}" with limit {limit:d}')
def step_when_search(context: Any, query: str, limit: int) -> None:
    # Handle async calls via scenario event loop:
    context.response = context.loop.run_until_complete(
        context.router.search(query=query, limit=limit)
    )


@then('the active provider should be "{expected_provider}"')
def step_then_provider(context: Any, expected_provider: str) -> None:
    assert context.response.provider == expected_provider


@then("the returned result count should be {count:d}")
def step_then_count(context: Any, count: int) -> None:
    assert len(context.response.results) == count
```

(Module and class names above are illustrative; use the real ones from PLAN.md once they exist.)

### Handling DataTables in Python
```python
@given("the following provider registry:")
def step_given_table(context: Any) -> None:
    # Iterate table rows as dicts:
    for row in context.table:
        provider = row["provider"]
        priority = int(row["priority"])
        enabled = row["enabled"].lower() == "true"
        context.registry.register(provider, priority=priority, enabled=enabled)
```

---

## 5. Environment Lifecycle Hooks (`tests/bdd/features/environment.py`)

Manage async event loops, client sessions, database connections, and cleanup:

```python
import asyncio
from typing import Any

import httpx


def before_all(context: Any) -> None:
    """Run once before any feature runs (e.g. test database init)."""
    context.config_data = {}


def before_scenario(context: Any, scenario: Any) -> None:
    """Isolate async event loop and HTTP sessions per scenario."""
    context.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(context.loop)
    context.http_client = httpx.AsyncClient(timeout=30.0)


def after_scenario(context: Any, scenario: Any) -> None:
    """Clean up open client connections and close the scenario event loop."""
    if getattr(context, "http_client", None) is not None:
        context.loop.run_until_complete(context.http_client.aclose())
    if getattr(context, "loop", None) is not None:
        context.loop.close()


def before_tag(context: Any, tag: str) -> None:
    """Execute setup only for specific tags (e.g. @database, @live)."""
    if tag == "live" and not getattr(context, "has_credentials", True):
        context.scenario.skip("Live credentials not available")
```

---

## 6. Troubleshoot Predictably

| Symptom | Cause | Action |
| :--- | :--- | :--- |
| **"Undefined Step" error** | Gherkin text does not match step decorator pattern | Run `uv run behave --dry-run` to print the exact template decorator; verify parameter types (`{limit:d}` vs `{text}`). |
| **`RuntimeError: Event loop is closed`** | Async task invoked outside active scenario loop | Wrap all async service/adapter calls with `context.loop.run_until_complete()`. |
| **State Leaks Between Scenarios** | Objects attached to `context` surviving scenario end | Reset scenario attributes in `before_scenario` or rely on `after_scenario` teardown. |
| **Step Times Out on External Network** | Default HTTP timeout exceeded | Set explicit timeout on `httpx.AsyncClient(timeout=30.0)` in `environment.py`. |
| **Skipped Scenarios not Printing Details** | Default output hides skipped step reasons | Run with `uv run behave --show-skipped` or `--no-skipped` as needed. |

---

## 7. Best Practices & Rules

- **Declarative over Imperative**: Express user value and business behavior (`When I route search request`), not UI click sequences or low-level variable assignments.
- **Tagging Strategy**: Tag scenarios by area (`@search`, `@routing`, `@pipeline`, `@storage`) and cost (`@live`, `@smoke`) for flexible execution.
- **Use Fakes by Default**: Wire ports with the fake adapters in `adapters/fake/`; reserve real providers for `@live` scenarios.
- **Isolate Scenarios**: Scenarios must never depend on the execution order or side-effects of preceding scenarios.
- **Exempt from Complexity Rules**: `pyproject.toml` contains `per-file-ignores` for `tests/**` (`C901`) to support multi-step validation flows.
