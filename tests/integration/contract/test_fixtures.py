"""The frontend fixtures must validate against the backend contracts."""

from pathlib import Path

import pytest

from hannovators_deep_researcher.models.contracts import GraphView, WorkspaceState

FIXTURES = Path(__file__).resolve().parents[3] / "frontend" / "src" / "test" / "fixtures"


@pytest.mark.integration
@pytest.mark.parametrize("domain", ["medical", "general"])
def test_frontend_fixtures_validate(domain: str) -> None:
    WorkspaceState.model_validate_json((FIXTURES / f"workspace.{domain}.json").read_text("utf-8"))
    GraphView.model_validate_json((FIXTURES / f"graph.{domain}.json").read_text("utf-8"))
