"""
Thin get-or-compute helper wrapping CacheProvider for read-heavy
endpoints (district/crime-type breakdowns, trends, forecasts,
sociological breakdown, repeat-offender list) that don't change until
new case data lands. Deliberately a plain function, not a decorator --
decorating FastAPI route functions risks interfering with FastAPI's
own signature introspection for query-param binding; an explicit call
inside each route body has no such risk and stays simple.

A cache miss/failure of any kind degrades to just computing fresh
(CacheProvider.get() already returns None rather than raising on
error) -- caching must never be the reason a request fails.
"""
import json
from typing import Any, Callable

from infrastructure.cache.cache_provider_factory import get_cache_provider

# This data only changes when new cases are seeded (a manual, infrequent
# operation), not via any write path in the running app -- a multi-hour
# TTL is safe and won't look "stuck" during a normal demo/dev session.
DEFAULT_EXPIRY_HOURS = 6


def cached_or_compute(key: str, compute: Callable[[], Any], expiry_hours: int = DEFAULT_EXPIRY_HOURS) -> Any:
    cache = get_cache_provider()
    cached = cache.get(key)
    if cached is not None:
        try:
            return json.loads(cached)
        except ValueError:
            pass  # corrupt/unexpected cached value -- fall through and recompute
    result = compute()
    cache.set(key, json.dumps(result, default=str), expiry_hours=expiry_hours)
    return result
