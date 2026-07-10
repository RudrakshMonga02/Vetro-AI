"""
ConversationMemory interface -- domain layer, zero external dependencies.
This is the seam that lets ChatService support context-aware follow-up
questions (explicit problem-statement requirement) without caring
whether history is stored in-process, in Catalyst Cache, or anywhere
else later:

  - In-memory (dev/local)  -> infrastructure/cache/in_memory_conversation_memory.py
  - Catalyst Cache          -> infrastructure/cache/catalyst_conversation_memory.py

Application code must only ever depend on this interface. Swapping the
storage backend means swapping which implementation the factory
constructs (infrastructure/cache/conversation_memory_factory.py), never
touching ChatService or the route.
"""
from abc import ABC, abstractmethod


class ConversationMemory(ABC):
    @abstractmethod
    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """Return [{'role': 'user'|'assistant', 'text': str}, ...] for
        this session, oldest first. Empty list if session is new/unknown."""
        ...

    @abstractmethod
    def append(self, session_id: str, role: str, text: str) -> None:
        """Add one turn to the session's history."""
        ...

    @abstractmethod
    def clear(self, session_id: str) -> None:
        """Wipe a session's history (e.g. user starts a new conversation)."""
        ...
