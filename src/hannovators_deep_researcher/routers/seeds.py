"""Seed uploads (PDF, PMID, DOI, URL). Not implemented yet."""

from fastapi import APIRouter, status

from hannovators_deep_researcher.routers.errors import api_error

router = APIRouter(prefix="/workspaces", tags=["seeds"])


@router.post("/{workspace_id}/seeds", status_code=status.HTTP_201_CREATED)
async def add_seed(workspace_id: str) -> None:
    raise api_error(
        status.HTTP_501_NOT_IMPLEMENTED, "NOT_IMPLEMENTED", "Seed upload is not implemented yet."
    )
