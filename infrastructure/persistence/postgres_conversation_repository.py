"""
Postgres implementation of ConversationRepository, using the SQLAlchemy
Conversation/Message models in db/models.py. Session-per-call pattern
matches postgres_repository.py for consistency.

OWNERSHIP: every method that touches a specific conversation_id filters
by owner_token in the same query that looks up the row, rather than
fetching by id first and checking the token after -- this means a
mismatched token and a nonexistent id produce the exact same "not
found" result via the exact same code path, so there's no timing or
behavioral difference an attacker could use to distinguish "wrong
token" from "id doesn't exist".
"""
from datetime import datetime, timezone
from typing import Any

from db.connection import get_session
from db.models import Conversation, Message
from domain.interfaces.conversation_repository import ConversationRepository

TITLE_MAX_LENGTH = 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _truncate_title(text: str) -> str:
    text = text.strip()
    if len(text) <= TITLE_MAX_LENGTH:
        return text
    return text[: TITLE_MAX_LENGTH - 1].rstrip() + "…"


class PostgresConversationRepository(ConversationRepository):

    def create_conversation(self, title: str, owner_token: str) -> dict[str, Any]:
        session = get_session()
        try:
            now = _utcnow()
            conv = Conversation(
                title=title, created_at=now, updated_at=now, owner_token=owner_token
            )
            session.add(conv)
            session.commit()
            session.refresh(conv)
            return {
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
            }
        finally:
            session.close()

    def list_conversations(self, owner_token: str) -> list[dict[str, Any]]:
        session = get_session()
        try:
            rows = (
                session.query(Conversation)
                .filter(Conversation.owner_token == owner_token)
                .order_by(Conversation.updated_at.desc())
                .all()
            )
            return [
                {"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()}
                for c in rows
            ]
        finally:
            session.close()

    def get_conversation(self, conversation_id: int, owner_token: str) -> dict[str, Any] | None:
        session = get_session()
        try:
            conv = (
                session.query(Conversation)
                .filter(
                    Conversation.id == conversation_id,
                    Conversation.owner_token == owner_token,
                )
                .first()
            )
            if conv is None:
                return None
            return {
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
            }
        finally:
            session.close()

    def get_messages(self, conversation_id: int, owner_token: str) -> list[dict[str, str]]:
        session = get_session()
        try:
            # Ownership check folded into the same query as the
            # existence check -- see module docstring for why this
            # matters (indistinguishable "not found" vs "not yours").
            conv = (
                session.query(Conversation)
                .filter(
                    Conversation.id == conversation_id,
                    Conversation.owner_token == owner_token,
                )
                .first()
            )
            if conv is None:
                return []

            rows = (
                session.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.timestamp.asc(), Message.id.asc())
                .all()
            )
            return [{"role": m.role, "text": m.content} for m in rows]
        finally:
            session.close()

    def append_message(self, conversation_id: int, role: str, content: str) -> None:
        # No owner_token param by design -- see interface docstring.
        # The route layer already verified ownership via
        # get_conversation() before ChatService (and therefore this
        # method) is ever reached for this request.
        session = get_session()
        try:
            msg = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                timestamp=_utcnow(),
            )
            session.add(msg)

            conv = session.get(Conversation, conversation_id)
            if conv is not None:
                conv.updated_at = _utcnow()
                if role == "user" and conv.title == "New Investigation":
                    conv.title = _truncate_title(content)

            session.commit()
        finally:
            session.close()

    def rename_conversation(self, conversation_id: int, title: str, owner_token: str) -> bool:
        session = get_session()
        try:
            conv = (
                session.query(Conversation)
                .filter(
                    Conversation.id == conversation_id,
                    Conversation.owner_token == owner_token,
                )
                .first()
            )
            if conv is None:
                return False
            conv.title = title
            conv.updated_at = _utcnow()
            session.commit()
            return True
        finally:
            session.close()

    def delete_conversation(self, conversation_id: int, owner_token: str) -> bool:
        session = get_session()
        try:
            conv = (
                session.query(Conversation)
                .filter(
                    Conversation.id == conversation_id,
                    Conversation.owner_token == owner_token,
                )
                .first()
            )
            if conv is None:
                return False
            session.delete(conv)  # cascades to messages, see relationship config
            session.commit()
            return True
        finally:
            session.close()
