"""
Catalyst Cache implementation of CacheProvider.

REST shape confirmed live against the real endpoint, not from the SDK's
own docstrings alone (the SDK's zcatalyst_sdk/cache/_segment.py shows
the same path/body shape, but its APP_DOMAIN constant is a placeholder
-- "https://console.catalyst.localzoho.com", not a real host -- so the
real domain still had to be confirmed separately, same issue as
QuickML's ACCOUNTS_URL placeholder):
    Base: https://api.catalyst.zoho.in/baas/v1/project/{project_id}/cache
    PUT:    POST body {"cache_name": key, "cache_value": value, "expiry_in_hours": N}
    GET:    ?cacheKey=<key> -> {"data": {"cache_value": "...", ...}}
    DELETE: ?cacheKey=<key>

Bypasses zcatalyst_sdk's Cache/Segment classes and initialize_app()
entirely, for the same reason as catalyst_quickml_provider.py -- see
infrastructure/catalyst_oauth.py's module docstring. A "Default"
segment already exists per-project with no console setup required
(confirmed live: writing to the bare /cache path, no segment id,
returned segment_details.segment_name == "Default" automatically).

Cache reads degrade to a miss (return None) on any error rather than
raising -- a broken cache should make a caller recompute, never break
the feature it's speeding up. Writes/deletes are best-effort for the
same reason: logged, not raised, so a transient Cache outage doesn't
turn a successful analytics query into a failed request.
"""
import logging

import requests

from domain.interfaces.cache_provider import CacheProvider
from infrastructure.catalyst_oauth import CatalystOAuthSession

_PROJECT_ID_ENV = "CATALYST_PROJECT_ID"
_logger = logging.getLogger(__name__)


class CatalystCacheProvider(CacheProvider):
    def __init__(self):
        import os

        project_id = os.getenv(_PROJECT_ID_ENV)
        if not project_id:
            raise RuntimeError(f"{_PROJECT_ID_ENV} is not set.")

        self._base_url = f"https://api.catalyst.zoho.in/baas/v1/project/{project_id}/cache"
        self._session = CatalystOAuthSession()

    def get(self, key: str) -> str | None:
        try:
            resp = requests.get(
                self._base_url,
                params={"cacheKey": key},
                headers=self._session.auth_headers(),
                timeout=15,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            value = resp.json().get("data", {}).get("cache_value")
            return value if isinstance(value, str) else None
        except Exception:
            _logger.warning("Catalyst Cache get(%r) failed, treating as a miss", key, exc_info=True)
            return None

    def set(self, key: str, value: str, expiry_hours: int = 1) -> None:
        try:
            resp = requests.post(
                self._base_url,
                json={"cache_name": key, "cache_value": value, "expiry_in_hours": expiry_hours},
                headers=self._session.auth_headers(),
                timeout=15,
            )
            resp.raise_for_status()
        except Exception:
            _logger.warning("Catalyst Cache set(%r) failed, continuing without caching it", key, exc_info=True)

    def delete(self, key: str) -> None:
        try:
            resp = requests.delete(
                self._base_url,
                params={"cacheKey": key},
                headers=self._session.auth_headers(),
                timeout=15,
            )
            resp.raise_for_status()
        except Exception:
            _logger.warning("Catalyst Cache delete(%r) failed", key, exc_info=True)
