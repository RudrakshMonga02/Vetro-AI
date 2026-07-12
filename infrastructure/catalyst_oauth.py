"""
Shared Zoho OAuth (refresh-token flow) access-token management for any
Catalyst service called directly via REST, deliberately bypassing
zcatalyst_sdk's initialize_app()/AuthorizedHttpClient machinery.

WHY THIS EXISTS, not just "why not use the SDK": confirmed by building
and testing infrastructure/llm/catalyst_quickml_provider.py --
initialize_app() requires CATALYST_OPTIONS with a non-empty project_key
(also called ZAID), which is validated locally by the SDK before any
network call, and which is genuinely costly to obtain (requires setting
up Catalyst Authentication with a social login provider configured --
a real, separate feature, not a quick console lookup). Tested calling
Catalyst REST endpoints directly with only an OAuth access token +ORG
header instead: works. ZAID/project_key turned out to be a client-side
SDK requirement, not something the real APIs enforce. So every provider
that only needs simple request/response calls (QuickML, Cache) shares
this session instead of paying the ZAID setup cost.

Every provider using this needs its own OAuth scope on the shared
CATALYST_AUTH credential (see .env's comment on that var for the
current combined scope list) -- this class doesn't care which scopes
are present, it just refreshes and hands back whatever token the
configured self-client is entitled to.
"""
import json
import os
import time

import requests

_AUTH_ENV = "CATALYST_AUTH"
_ORG_ID_ENV = "X_ZOHO_CATALYST_ORG_ID"

# This project's data center -- confirmed from every working endpoint
# used so far (api.catalyst.zoho.in, accounts.zoho.in). Not derived
# generically; if this app ever moves data centers, this needs updating.
_ACCOUNTS_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"

# Refresh a little before actual expiry, not exactly at it, so a
# request never lands in-flight right as the token dies.
_REFRESH_SAFETY_MARGIN_SECONDS = 60


class CatalystOAuthSession:
    """Construct one per provider instance. Access tokens are cached
    in-memory and only refreshed once actually expired -- a normal
    request doesn't cost an extra OAuth round-trip."""

    def __init__(self):
        auth_json = os.getenv(_AUTH_ENV)
        org_id = os.getenv(_ORG_ID_ENV)
        if not auth_json:
            raise RuntimeError(f"{_AUTH_ENV} is not set.")
        if not org_id:
            raise RuntimeError(
                f"{_ORG_ID_ENV} is not set -- Catalyst REST APIs called this way "
                "have been confirmed to require it (ORGID_HEADER_UNAVAILABLE without)."
            )

        auth = json.loads(auth_json)
        self._client_id = auth["client_id"]
        self._client_secret = auth["client_secret"]
        self._refresh_token = auth["refresh_token"]
        self.org_id = org_id

        self._access_token: str | None = None
        self._access_token_expires_at: float = 0.0

    def get_access_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expires_at:
            return self._access_token

        resp = requests.post(
            _ACCOUNTS_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"Catalyst OAuth token refresh failed: {data.get('error', data)}")

        self._access_token = data["access_token"]
        self._access_token_expires_at = (
            time.time() + data.get("expires_in", 3600) - _REFRESH_SAFETY_MARGIN_SECONDS
        )
        return self._access_token

    def auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Zoho-oauthtoken {self.get_access_token()}",
            "CATALYST-ORG": self.org_id,
        }
