"""
Factory for ConversationRepository. Currently only Postgres is
implemented -- unlike CaseRepository's factory, this doesn't branch on
DATA_BACKEND yet, since conversations are new and there's no existing
Catalyst-backed conversation storage to switch to. Structured the same
way anyway (a factory function, not direct instantiation in
ChatService) so adding a Catalyst implementation later means adding a
branch here, not touching callers.
"""
from domain.interfaces.conversation_repository import ConversationRepository


def get_conversation_repository() -> ConversationRepository:
    from infrastructure.persistence.postgres_conversation_repository import (
        PostgresConversationRepository,
    )
    return PostgresConversationRepository()
