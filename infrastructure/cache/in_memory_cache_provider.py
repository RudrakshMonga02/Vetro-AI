"""
In-memory CacheProvider -- dev default, works today, single-instance
only (same documented limitation every prior in-memory piece in this
project has had: fine for local dev/one AppSail instance, not safe once
there's more than one process/instance sharing state, since each
process gets its own independent dict). Swap to CatalystCacheProvider
before relying on cross-instance consistency.
"""
import time

from domain.interfaces.cache_provider import CacheProvider


class InMemoryCacheProvider(CacheProvider):
    def __init__(self):
        self._store: dict[str, tuple[str, float]] = {}  # key -> (value, expires_at)

    def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: str, expiry_hours: int = 1) -> None:
        self._store[key] = (value, time.time() + expiry_hours * 3600)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
