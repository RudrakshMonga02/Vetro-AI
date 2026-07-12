"""
Factory that decides which CacheProvider implementation to hand out,
based on the RESPONSE_CACHE_BACKEND env var. Same pattern as every
other factory in this app (repository_factory.py, llm_factory.py).

Named RESPONSE_CACHE_BACKEND, not CACHE_BACKEND, deliberately -- the
older CACHE_BACKEND var belonged to a now-removed ConversationMemory
abstraction (chat history caching, superseded by the Postgres-backed
ConversationRepository); this is a different, currently-used concern
(memoizing analytics-style read results), and reusing the old name
risked confusion between two different interfaces.

Singleton: a fresh CatalystCacheProvider per call would mean a fresh
CatalystOAuthSession per call too, throwing away the cached access
token every time -- defeats the point of caching it. One shared
instance per process, same reasoning as the old conversation-memory
factory's singleton (still valid even though that specific factory's
gone).
"""
import os

from domain.interfaces.cache_provider import CacheProvider

_singleton: CacheProvider | None = None


def get_cache_provider() -> CacheProvider:
    global _singleton
    if _singleton is not None:
        return _singleton

    backend = os.getenv("RESPONSE_CACHE_BACKEND", "in_memory").lower()

    if backend == "in_memory":
        from infrastructure.cache.in_memory_cache_provider import InMemoryCacheProvider
        _singleton = InMemoryCacheProvider()
        return _singleton

    if backend == "catalyst":
        from infrastructure.cache.catalyst_cache_provider import CatalystCacheProvider
        _singleton = CatalystCacheProvider()
        return _singleton

    raise ValueError(f"Unknown RESPONSE_CACHE_BACKEND: {backend!r} (expected 'in_memory' or 'catalyst')")
