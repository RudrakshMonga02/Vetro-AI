"""
Factory that decides which ConversationMemory implementation to hand
out, based on the CACHE_BACKEND env var.

Usage:
    CACHE_BACKEND=in_memory        -> InMemoryConversationMemory (current default)
    CACHE_BACKEND=catalyst_cache   -> CatalystConversationMemory (not yet implemented)

IMPORTANT: unlike the repository/LLM factories, this one returns a
SINGLETON for the in-memory backend. ChatService is constructed fresh
per-request (see api/routes/chat.py), so if this factory built a new
InMemoryConversationMemory() every call, every request would get a
blank memory and follow-up questions would never actually see prior
turns -- defeating the entire point. Catalyst Cache doesn't have this
problem since it's externally shared, but singleton-ing it too is
harmless and cheap.
"""
import os

from domain.interfaces.conversation_memory import ConversationMemory

_singleton: ConversationMemory | None = None


def get_conversation_memory() -> ConversationMemory:
    global _singleton
    if _singleton is not None:
        return _singleton

    backend = os.getenv("CACHE_BACKEND", "in_memory").lower()

    if backend == "in_memory":
        from infrastructure.cache.in_memory_conversation_memory import InMemoryConversationMemory
        _singleton = InMemoryConversationMemory()
        return _singleton

    if backend == "catalyst_cache":
        from infrastructure.cache.catalyst_conversation_memory import CatalystConversationMemory
        _singleton = CatalystConversationMemory()
        return _singleton

    raise ValueError(f"Unknown CACHE_BACKEND: {backend!r} (expected 'in_memory' or 'catalyst_cache')")
