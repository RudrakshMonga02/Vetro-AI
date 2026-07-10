"""
PLACEHOLDER -- not implemented yet.

Catalyst Cache implementation of ConversationMemory. This is the
correct long-term home for session history per the Catalyst-first
policy (docs/PRD.md section 4: "Cache" capability -> Catalyst Cache),
and it also fixes the multi-instance limitation that
InMemoryConversationMemory has (see that file's docstring) -- Catalyst
Cache is shared/external, so any AppSail instance can read/write the
same session.

NOTE: untested against a real Catalyst project -- verify the exact
cache SDK method names/signatures once credentials exist. Expected
shape, based on Catalyst's Python SDK cache component docs:
    cache = app.cache()
    segment = cache.segment()  # or a named segment
    segment.put(key, value, expiry_in_minutes=...)
    segment.get(key)
    segment.delete(key)

Design choice: store each session's history as ONE JSON-serialized
list under one cache key (`conversation:{session_id}`), rather than
one cache entry per turn. Simpler to reason about, and Catalyst Cache
entries are key->value, not naturally list-appendable, so
read-modify-write on a single JSON blob is the natural fit.
"""
import json

from domain.interfaces.conversation_memory import ConversationMemory

MAX_TURNS_PER_SESSION = 20
SESSION_TTL_MINUTES = 120


class CatalystConversationMemory(ConversationMemory):
    def __init__(self):
        raise NotImplementedError(
            "CatalystConversationMemory not yet implemented -- wire this up "
            "once Catalyst Cache credentials are confirmed working locally "
            "(see docs/PRD.md Catalyst setup notes). Use "
            "CACHE_BACKEND=in_memory in .env until then."
        )

    def _key(self, session_id: str) -> str:
        return f"conversation:{session_id}"

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        raise NotImplementedError

    def append(self, session_id: str, role: str, text: str) -> None:
        raise NotImplementedError

    def clear(self, session_id: str) -> None:
        raise NotImplementedError
