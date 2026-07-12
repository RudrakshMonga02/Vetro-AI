"""
CacheProvider interface -- domain layer, zero external dependencies.
For memoizing expensive/repeated read results (analytics aggregates,
sociological breakdowns, repeat-offender lists) that don't change until
new case data lands, not for the chat/conversation history path (that's
ConversationRepository, a different concern entirely -- persisted
source of truth, not a cache).

Values are plain strings, matching the real constraint of Catalyst's
Cache service (cache_value is string-typed on the wire) -- callers
json.dumps()/json.loads() their own payloads rather than this interface
trying to abstract that away.

  - In-memory (dev default) -> infrastructure/cache/in_memory_cache_provider.py
  - Catalyst Cache           -> infrastructure/cache/catalyst_cache_provider.py

Application code must only ever depend on this interface. Swapping
backends means swapping which implementation the factory constructs
(infrastructure/cache/cache_provider_factory.py), never touching
calling code.
"""
from abc import ABC, abstractmethod


class CacheProvider(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None:
        """Return the cached value for key, or None if missing/expired."""
        ...

    @abstractmethod
    def set(self, key: str, value: str, expiry_hours: int = 1) -> None:
        """Store value under key, expiring after expiry_hours."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove key if present. No-op if it isn't -- callers shouldn't
        need to check existence first just to invalidate a cache entry."""
        ...
