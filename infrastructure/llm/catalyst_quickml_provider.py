"""
Catalyst QuickML LLM Serving implementation of LLMProvider.

Everything below is confirmed by actually calling the real, deployed
GLM 4.7 Flash endpoint and reading the real response -- not the
console's sample request/response, which turned out to describe a
different (OpenAI-compatible chat-completions) response shape than
what this endpoint genuinely returns.

REQUEST shape (confirmed correct against the real endpoint):
    {"model": "...", "messages": [{"role","content"}, ...],
     "max_tokens", "temperature", "stream": false,
     "chat_template_kwargs": {"enable_thinking": bool}}

RESPONSE shape (confirmed live -- NOT choices[0].message.content,
despite that being what the console's sample response showed):
    {"response": "<the actual answer text>", "tool_calls": [...],
     "usage": {...}, "model": "...", "created_time": <float>}

CALL PATH -- deliberately does NOT use zcatalyst_sdk's initialize_app()/
quick_ml().predict() machinery at all, for two confirmed reasons:
  1. predict() POSTs to a generic '/endpoints/predict' path with a
     X-QUICKML-ENDPOINT-KEY header -- a different URL family entirely
     from the direct per-model chat endpoint the console actually gives
     you (.../quickml/v1/project/{id}/glm/chat). Trusting predict() to
     route there would be guessing.
  2. initialize_app() requires CATALYST_OPTIONS with a non-empty
     project_key (Catalyst's internal name for a value also called
     ZAID) -- validated locally by the SDK before any network call.
     Getting a real ZAID requires setting up Catalyst Authentication
     with a social login provider configured, a genuinely separate
     piece of work. BUT: calling the endpoint directly (this file's
     approach) was tested live and works with only an OAuth access
     token and one header -- ZAID/project_key is not actually needed
     by the real API, only by the SDK's own client-side validation.
     Since the SDK path adds a real setup cost for a check the actual
     API doesn't enforce, this bypasses the SDK for HTTP entirely and
     talks to Zoho's OAuth + the endpoint directly.

Confirmed requirements, all live-tested, not assumed:
  - Auth: standard Zoho OAuth refresh-token flow (self-client
    registered at the regional API Console, NOT `catalyst token:generate`
    -- that CLI command produces a different kind of token for CLI-to-
    CLI remote auth, confirmed by testing it and getting a credential
    shape that fit neither of zcatalyst_sdk's supported types).
  - OAuth scope: exactly "QuickML.deployment.READ" -- QuickML uniquely
    uses a "QuickML." prefix, not the "ZohoCatalyst." prefix almost
    every other Catalyst service scope uses. "ZohoCatalyst.fullaccess.ALL"
    was tried first and rejected with INVALID_OAUTHSCOPE.
  - A "CATALYST-ORG" header carrying the Zoho Organization ID is
    mandatory for this endpoint specifically -- omitting it fails with
    ORGID_HEADER_UNAVAILABLE even with valid auth + correct scope. Found
    live in the console's org menu (for this account, it happens to
    equal the Development environment ID, 60074029060 -- not assumed to
    be true in general, just true for this project).
  - Token endpoint is region-specific: https://accounts.zoho.in for this
    project's data center, not the generic .com used in generic examples.

Design choices carried over from the LLMProvider interface:
  - generate()'s single `prompt` string becomes one "user" message with
    a minimal generic system message, rather than restructuring every
    caller (chat_service.py, query_rewriter.py, etc.) to build a proper
    messages array -- matches how GeminiProvider already just sends the
    whole prompt as one blob.
  - `tools`/`tool_choice` are omitted -- no function-calling use case
    here, despite the endpoint supporting it.
  - `chat_template_kwargs.enable_thinking` defaults to False -- GLM's
    extended-thinking mode is for complex multi-step reasoning, not the
    RAG-grounded QA/classification/extraction tasks this app uses the
    LLM for, and leaving it on risks visible "thinking" text leaking
    into what should be a clean answer.
  - NOT TRUE TOKEN STREAMING: this always sends stream=false and fakes
    a stream by chunking the finished response word-by-word, so Chat's
    existing live-typing UI still works. Real SSE streaming would need
    a streaming-capable request call parsing a chunked event-stream
    response instead of one JSON body -- not attempted here.
  - Access tokens are cached in-memory with expiry tracking (Zoho's
    typically last ~1hr) so a fresh chat message doesn't cost an extra
    OAuth round-trip every time -- only refreshed when actually expired.
"""
import os
import time
from typing import AsyncIterator

import requests

from domain.interfaces.llm_provider import LLMProvider

_ENDPOINT_URL_ENV = "QUICKML_ENDPOINT_URL"
_MODEL_ENV = "QUICKML_MODEL"
_AUTH_ENV = "CATALYST_AUTH"
_ORG_ID_ENV = "X_ZOHO_CATALYST_ORG_ID"

# This project's data center -- confirmed from every endpoint/accounts
# URL used so far (api.catalyst.zoho.in, accounts.zoho.in). Not derived
# generically; if this app ever moves data centers, this needs updating.
_ACCOUNTS_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"

_MAX_TOKENS = 2048  # higher than the console sample's 500 -- this app's
                     # Markdown-formatted analytical answers (district
                     # breakdowns, lists) can run long; a truncated
                     # answer is a correctness bug, not just a style one.

# Refresh a little before actual expiry, not exactly at it, to avoid a
# request landing in-flight right as the token dies.
_REFRESH_SAFETY_MARGIN_SECONDS = 60


class CatalystQuickMLProvider(LLMProvider):
    def __init__(self):
        import json

        endpoint_url = os.getenv(_ENDPOINT_URL_ENV)
        model = os.getenv(_MODEL_ENV)
        auth_json = os.getenv(_AUTH_ENV)
        org_id = os.getenv(_ORG_ID_ENV)

        if not endpoint_url:
            raise RuntimeError(f"{_ENDPOINT_URL_ENV} is not set.")
        if not model:
            raise RuntimeError(f"{_MODEL_ENV} is not set.")
        if not auth_json:
            raise RuntimeError(f"{_AUTH_ENV} is not set.")
        if not org_id:
            raise RuntimeError(
                f"{_ORG_ID_ENV} is not set -- the endpoint returns "
                "ORGID_HEADER_UNAVAILABLE without it."
            )

        auth = json.loads(auth_json)
        self._client_id = auth["client_id"]
        self._client_secret = auth["client_secret"]
        self._refresh_token = auth["refresh_token"]
        self._endpoint_url = endpoint_url
        self._model = model
        self._org_id = org_id

        self._access_token: str | None = None
        self._access_token_expires_at: float = 0.0

    def _get_access_token(self) -> str:
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

    async def generate(self, prompt: str) -> str:
        access_token = self._get_access_token()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": _MAX_TOKENS,
            "temperature": 0.7,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        resp = requests.post(
            self._endpoint_url,
            json=payload,
            headers={
                "Authorization": f"Zoho-oauthtoken {access_token}",
                "CATALYST-ORG": self._org_id,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        if "response" not in data:
            raise ValueError(f"Unrecognized QuickML response shape: {data!r}")
        return data["response"]

    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        full_text = await self.generate(prompt)
        # Fake streaming -- see module docstring.
        words = full_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
