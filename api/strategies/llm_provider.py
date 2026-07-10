"""
LLM provider abstraction. Lets us swap Gemini-direct for a
Catalyst-QuickML-wrapped call later without touching ChatService or
the route -- resolves the open compliance question from earlier
without committing to an answer now.
"""
import os
from abc import ABC, abstractmethod
from typing import AsyncIterator

from dotenv import load_dotenv
from google import genai

load_dotenv()


class LLMProvider(ABC):
    @abstractmethod
    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        """Yield text chunks as they're generated."""
        ...


class GeminiProvider(LLMProvider):
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = model

    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        # google-genai's streaming call is sync-generator based;
        # wrap it so the route's async StreamingResponse can consume it.
        stream = self.client.models.generate_content_stream(model=self.model, contents=prompt)
        for chunk in stream:
            if chunk.text:
                yield chunk.text


class CatalystQuickMLProvider(LLMProvider):
    """
    PLACEHOLDER -- not implemented. Wire this up once the QuickML-RAG
    compliance question is resolved with organizers. Should implement
    the same stream_generate() interface so ChatService doesn't change.
    """
    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        raise NotImplementedError("CatalystQuickMLProvider not yet implemented")
        yield  # pragma: no cover -- keeps this an async generator


def get_llm_provider() -> LLMProvider:
    backend = os.getenv("LLM_BACKEND", "gemini").lower()
    if backend == "gemini":
        return GeminiProvider()
    if backend == "catalyst_quickml":
        return CatalystQuickMLProvider()
    raise ValueError(f"Unknown LLM_BACKEND: {backend!r}")
