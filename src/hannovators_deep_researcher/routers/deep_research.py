"""Tavily deep research API. Owned by lane `research-quality` (PLAN.md section 7.9).

Contract (PLAN.md section 5.3):
- POST /workspaces/{id}/deep-research -> 202 DeepResearchRecord (409 while one is running)
- GET  /workspaces/{id}/deep-research -> DeepResearchRecord (404 when none was started)
"""

from fastapi import APIRouter, status

from hannovators_deep_researcher.models.deep_research import DeepResearchRecord
from hannovators_deep_researcher.routers.errors import api_error

router = APIRouter(prefix="/workspaces", tags=["deep-research"])

_NOT_YET = "Deep research is not implemented yet."


@router.post("/{workspace_id}/deep-research", status_code=status.HTTP_202_ACCEPTED)
async def start_deep_research(workspace_id: str) -> DeepResearchRecord:
    raise api_error(status.HTTP_501_NOT_IMPLEMENTED, "NOT_IMPLEMENTED", _NOT_YET)


@router.get("/{workspace_id}/deep-research")
async def get_deep_research(workspace_id: str) -> DeepResearchRecord:
    raise api_error(status.HTTP_501_NOT_IMPLEMENTED, "NOT_IMPLEMENTED", _NOT_YET)
