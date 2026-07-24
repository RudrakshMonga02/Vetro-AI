"""
Chatbot route. Streams tokens back as they're generated.

conversation_id is REQUIRED, not an optional auto-generated session_id
-- the frontend must create a conversation first via POST
/conversations (see api/routes/conversations.py), then send every
message in that thread with the returned id. This is what gives each
"Investigation A/B/C..." thread genuinely independent, persisted
memory (Postgres, not an in-process cache -- see
infrastructure/persistence/postgres_conversation_repository.py).

OWNERSHIP + RATE LIMITING, added per the vulnerability review in
docs/PRD.md:
  - X-Owner-Token header required and checked against the
    conversation, same as every other conversations.py route -- a
    wrong/missing token 404s, same as an unknown conversation_id.
  - Rate-limited per IP (see api/main.py's Limiter setup), since this
    route triggers a real, billed Gemini call per request and
    previously had zero throttling in front of it.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.rate_limiter import limiter as _limiter
from api.middleware.auth import OfficerContext, get_current_officer
from api.routes.conversations import require_owner_token, scoped_owner_token
from api.services.chat_service import ChatService
from infrastructure.persistence.conversation_repository_factory import (
    get_conversation_repository,
)

router = APIRouter()

# Generous enough for a genuine investigative question, tight enough
# to bound worst-case prompt size / LLM cost per request. Adjust if
# real usage shows legitimate queries getting clipped.
QUERY_MAX_LENGTH = 2000


class ChatRequest(BaseModel):
    query: str = Field(max_length=QUERY_MAX_LENGTH)
    conversation_id: int
    language: Literal["en", "kn"] = Field(
        default="en",
        description="Language for the investigator-facing response.",
    )


@router.post("/")
@_limiter.limit("10/minute")
async def chat(
    request: Request,  # required as the first param for slowapi's decorator to find the client IP
    body: ChatRequest,
    owner_token: str = Depends(require_owner_token),
    officer: OfficerContext = Depends(get_current_officer),
):
    # Fail fast with a clear 404 rather than silently creating orphaned
    # messages against a conversation_id that doesn't exist (or isn't
    # owned by this token) -- a stale id, or someone else's id, should
    # surface as "not found", not succeed into nowhere or leak
    # existence via a different error code.
    repo = get_conversation_repository()
    owner_token = scoped_owner_token(officer, owner_token)
    if repo.get_conversation(body.conversation_id, owner_token) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    service = ChatService()

    async def generate():
        async for chunk in service.stream_answer(
            body.query,
            body.conversation_id,
            owner_token,
            language=body.language,
            officer=officer,
        ):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")
