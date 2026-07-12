"""
ConversationRepository interface -- domain layer, zero external
dependencies. Mirrors the CaseRepository pattern (see
domain/interfaces/case_repository.py) for consistency, even though
Postgres is the only implementation that exists right now -- a
Catalyst Data Store implementation can be added later the same way
CatalystCaseRepository was, without touching application code.

This is the single source of truth for chat history -- it REPLACES
the old ConversationMemory cache abstraction (infrastructure/cache/)
as what ChatService reads from and writes to. That cache abstraction
still exists in the codebase but is no longer wired into ChatService;
see docs/PRD.md decision log for why.

OWNERSHIP, added per the vulnerability review (docs/PRD.md): every
method that reads or mutates a specific conversation takes an
owner_token and must treat a token mismatch IDENTICALLY to the
conversation not existing (return None / raise not-found), never a
distinct "forbidden" signal -- that would leak whether a given id
exists to someone who doesn't own it. This is a stopgap ownership
check, not real multi-user auth (see db/models.py's Conversation
docstring) -- replace with Catalyst Authentication + real user
accounts before this handles real data.
"""
from abc import ABC, abstractmethod
from typing import Any


class ConversationRepository(ABC):
    @abstractmethod
    def create_conversation(self, title: str, owner_token: str) -> dict[str, Any]:
        """Create a new, empty conversation tagged with the given
        owner_token. Returns {'id', 'title', 'created_at', 'updated_at'}.

        owner_token is supplied by the CALLER (client-generated once
        per device/browser -- see api/routes/conversations.py), not
        generated here. This is deliberate: if the server minted a
        fresh token per conversation, list_conversations(token) could
        never return more than the one conversation that happened to
        get that exact token -- the whole point of one shared
        device-level token is that ALL of that device's conversations
        share it, so listing "my conversations" actually works."""
        ...

    @abstractmethod
    def list_conversations(self, owner_token: str) -> list[dict[str, Any]]:
        """Return only conversations owned by this token, as
        [{'id', 'title', 'updated_at'}, ...], ordered most-recently-
        updated first -- this ordering is what the sidebar displays
        directly, don't re-sort client-side."""
        ...

    @abstractmethod
    def get_conversation(self, conversation_id: int, owner_token: str) -> dict[str, Any] | None:
        """Return {'id', 'title', 'created_at', 'updated_at'} for one
        conversation, or None if it doesn't exist OR owner_token
        doesn't match -- these two cases must be indistinguishable to
        the caller, to avoid leaking existence of ids you don't own."""
        ...

    @abstractmethod
    def get_messages(self, conversation_id: int, owner_token: str) -> list[dict[str, Any]]:
        """Return [{'role': 'user'|'assistant', 'text': str,
        'citations': list[dict] | None}, ...] for this conversation,
        oldest first. citations is None for every user message and for
        assistant messages that never had any (SQL/entity-list answers,
        or anything persisted before the citations column existed).
        Empty list if the conversation has no messages, doesn't exist,
        or owner_token doesn't match."""
        ...

    @abstractmethod
    def append_message(
        self, conversation_id: int, role: str, content: str, citations: list[dict[str, Any]] | None = None
    ) -> None:
        """Add one message to the conversation and bump updated_at.
        citations is only ever meaningful for role="assistant" -- pass
        None for user messages and for assistant answers with none.
        No owner_token here by design: this is only ever called from
        ChatService AFTER the route layer has already verified
        ownership via get_conversation() for this request -- see
        api/routes/chat.py. Re-checking here would be redundant, not
        safer."""
        ...

    @abstractmethod
    def rename_conversation(self, conversation_id: int, title: str, owner_token: str) -> bool:
        """Returns True if renamed, False if the conversation doesn't
        exist or owner_token doesn't match (caller should 404 either way)."""
        ...

    @abstractmethod
    def delete_conversation(self, conversation_id: int, owner_token: str) -> bool:
        """Returns True if deleted, False if the conversation doesn't
        exist or owner_token doesn't match (caller should 404 either way)."""
        ...
