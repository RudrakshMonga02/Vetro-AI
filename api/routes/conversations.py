"""
Conversation CRUD -- backs the sidebar's "Investigation A/B/C..." list.
Each conversation has its own persisted message history in Postgres
(see db/models.py's Conversation/Message tables); this is what makes
each thread's memory genuinely independent, not just a UI-level filter
over one shared history.

OWNERSHIP: every route except create_conversation requires an
X-Owner-Token header matching the token returned when the conversation
was created. A missing token is a 401 (nothing to distinguish a probe
attempt from). A wrong token for a real conversation_id gets the SAME
404 as a nonexistent id -- never a distinct 403 -- so a caller without
the right token can't tell whether a given id exists. See
docs/PRD.md vulnerability review + db/models.py's Conversation
docstring for why this is a stopgap, not real multi-user auth.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from infrastructure.persistence.conversation_repository_factory import (
    get_conversation_repository,
)

router = APIRouter()

_OWNER_TOKEN_MAX_LEN = 128  # generous headroom over token_urlsafe(32)'s 43 chars


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class RenameConversationRequest(BaseModel):
    title: str = Field(max_length=200)


def require_owner_token(
    x_owner_token: str | None = Header(default=None, max_length=_OWNER_TOKEN_MAX_LEN)
) -> str:
    """FastAPI dependency: every route below except create_conversation
    uses this instead of repeating the same header-presence check."""
    if not x_owner_token:
        raise HTTPException(status_code=401, detail="X-Owner-Token header is required")
    return x_owner_token


@router.post("")
def create_conversation(
    request: CreateConversationRequest = CreateConversationRequest(),
    owner_token: str = Depends(require_owner_token),
):
    repo = get_conversation_repository()
    title = request.title or "New Investigation"
    # owner_token comes from the client (one generated per
    # device/browser on first app load -- see vetro-ai-frontend's
    # ChatApp.jsx) so that ALL of a device's conversations share the
    # same token and list_conversations() can return all of them in
    # one call. See ConversationRepository.create_conversation's
    # docstring for why this can't be server-generated per-conversation.
    return repo.create_conversation(title=title, owner_token=owner_token)


@router.get("")
def list_conversations(owner_token: str = Depends(require_owner_token)):
    repo = get_conversation_repository()
    return repo.list_conversations(owner_token)


@router.get("/{conversation_id}/messages")
def get_messages(conversation_id: int, owner_token: str = Depends(require_owner_token)):
    repo = get_conversation_repository()
    conv = repo.get_conversation(conversation_id, owner_token)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return repo.get_messages(conversation_id, owner_token)


@router.patch("/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    request: RenameConversationRequest,
    owner_token: str = Depends(require_owner_token),
):
    repo = get_conversation_repository()
    renamed = repo.rename_conversation(conversation_id, request.title, owner_token)
    if not renamed:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"id": conversation_id, "title": request.title}


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: int, owner_token: str = Depends(require_owner_token)):
    repo = get_conversation_repository()
    deleted = repo.delete_conversation(conversation_id, owner_token)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True}
