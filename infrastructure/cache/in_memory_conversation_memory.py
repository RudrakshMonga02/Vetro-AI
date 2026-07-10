"""
In-memory implementation of ConversationMemory. Good for local dev and
for right now, since Catalyst Cache isn't wired with real credentials
yet (see infrastructure/cache/catalyst_conversation_memory.py).

LIMITATION, by design: this only persists for the lifetime of the
running process -- a server restart wipes all sessions, and it will
NOT work correctly if the app is ever scaled to multiple instances
(each instance would have its own separate memory, so a user's
follow-up question could land on an instance that never saw their
first question). This is exactly the kind of limitation that goes
away once CatalystConversationMemory is wired up, since Catalyst Cache
is shared/external. Fine for a single-instance local dev/demo; not
fine for the actual AppSail deployment once traffic could hit
multiple instances -- track that as a pre-deployment blocker.
"""
import time
from threading import Lock

from domain.interfaces.conversation_memory import ConversationMemory

# Keep memory bounded -- without this, a long-running dev server with
# many chat sessions (or one very long conversation) would grow
# unboundedly. Matches "last N turns" being enough for follow-up
# context; older turns just age out.
MAX_TURNS_PER_SESSION = 20
SESSION_TTL_SECONDS = 60 * 60 * 2  # 2 hours of inactivity -> session forgotten


class InMemoryConversationMemory(ConversationMemory):
    def __init__(self):
        self._sessions: dict[str, list[dict[str, str]]] = {}
        self._last_touched: dict[str, float] = {}
        self._lock = Lock()

    def _evict_stale(self) -> None:
        now = time.time()
        stale = [
            sid for sid, ts in self._last_touched.items()
            if now - ts > SESSION_TTL_SECONDS
        ]
        for sid in stale:
            self._sessions.pop(sid, None)
            self._last_touched.pop(sid, None)

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            self._evict_stale()
            return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, role: str, text: str) -> None:
        with self._lock:
            history = self._sessions.setdefault(session_id, [])
            history.append({"role": role, "text": text})
            if len(history) > MAX_TURNS_PER_SESSION:
                del history[: len(history) - MAX_TURNS_PER_SESSION]
            self._last_touched[session_id] = time.time()

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._last_touched.pop(session_id, None)
