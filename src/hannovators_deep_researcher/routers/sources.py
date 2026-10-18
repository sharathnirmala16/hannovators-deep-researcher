"""Source detail API. Owned by lane `platform` (PLAN.md section 7.9).

Contract (PLAN.md section 5.3):
- GET /workspaces/{id}/sources/{source_id} -> SourceDetail
"""

from fastapi import APIRouter, status

from hannovators_deep_researcher.models.contracts import SourceDetail
from hannovators_deep_researcher.routers.errors import api_error

router = APIRouter(prefix="/workspaces", tags=["sources"])


@router.get("/{workspace_id}/sources/{source_id}")
async def get_source(workspace_id: str, source_id: str) -> SourceDetail:
    raise api_error(
        status.HTTP_501_NOT_IMPLEMENTED, "NOT_IMPLEMENTED", "Source detail is not implemented yet."
    )
