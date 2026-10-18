"""Grounded chat API. Owned by lane `grounding` (PLAN.md section 7.9).

Contract (PLAN.md section 5.3):
- GET  /workspaces/{id}/chat -> list[ChatMessageView] (oldest first)
- POST /workspaces/{id}/chat (ChatRequest) -> ChatMessageView (the assistant answer; the user
       message is stored too). Every factual sentence carries `[n]` citations.
"""

from fastapi import APIRouter

from hannovators_deep_researcher.models.chat import ChatMessageView, ChatRequest
from hannovators_deep_researcher.routers.dependencies import Container
from hannovators_deep_researcher.services.chat import ChatService

router = APIRouter(prefix="/workspaces", tags=["chat"])


@router.get("/{workspace_id}/chat")
async def list_chat(workspace_id: str, container: Container) -> list[ChatMessageView]:
    await container.state.require_workspace(workspace_id)
    return await ChatService(container.services).list_messages(workspace_id)


@router.post("/{workspace_id}/chat")
async def ask(workspace_id: str, body: ChatRequest, container: Container) -> ChatMessageView:
    await container.state.require_workspace(workspace_id)
    return await ChatService(container.services).ask(workspace_id, body.question)
