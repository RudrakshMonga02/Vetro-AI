"""
PLACEHOLDER -- not implemented yet.

Catalyst QuickML LLM Serving implementation of LLMProvider. Wire this
up using Catalyst's OAuth-authenticated REST API for hosted models
(Qwen 2.5-14B-Instruct etc.) once credentials/access are confirmed --
see docs/PRD.md section 4.3 for the QuickML RAG early-access risk note
(LLM Serving itself is believed lower-risk / not access-gated, but
verify against a real Catalyst project before relying on that).

Must implement the same stream_generate() interface as GeminiProvider
so ChatService and any use-case code needs zero changes when this
becomes real -- that's the entire point of the LLMProvider interface.
"""
from typing import AsyncIterator

from domain.interfaces.llm_provider import LLMProvider


class CatalystQuickMLProvider(LLMProvider):
    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        raise NotImplementedError("CatalystQuickMLProvider not yet implemented")
        yield  # pragma: no cover -- keeps this an async generator

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError("CatalystQuickMLProvider not yet implemented")
