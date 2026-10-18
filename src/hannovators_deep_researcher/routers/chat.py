"""Grounded chat API. Owned by lane `grounding` (PLAN.md section 7.9).

Contract (PLAN.md section 5.3):
- GET  /workspaces/{id}/chat -> list[ChatMessageView] (oldest first)
- POST /workspaces/{id}/chat (ChatRequest) -> ChatMessageView (the assistant answer; the user
       message is stored too). Every factual sentence carries `[n]` citations.
"""

from fastapi import APIRouter, status

from hannovators_deep_researcher.models.chat import ChatMessageView, ChatRequest
from hannovators_deep_researcher.routers.errors import api_error

router = APIRouter(prefix="/workspaces", tags=["chat"])

_NOT_YET = "Chat is not implemented yet."


@router.get("/{workspace_id}/chat")
async def list_chat(workspace_id: str) -> list[ChatMessageView]:
    raise api_error(status.HTTP_501_NOT_IMPLEMENTED, "NOT_IMPLEMENTED", _NOT_YET)


@router.post("/{workspace_id}/chat")
async def ask(workspace_id: str, body: ChatRequest) -> ChatMessageView:
    raise api_error(status.HTTP_501_NOT_IMPLEMENTED, "NOT_IMPLEMENTED", _NOT_YET)
