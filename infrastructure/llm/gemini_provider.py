"""
Gemini implementation of LLMProvider. This is the only file in the
whole app that imports google-genai directly -- if Gemini's SDK changes
its API shape, this is the only place that needs to change.
"""
import os
from typing import AsyncIterator

from dotenv import load_dotenv
from google import genai
from google.genai import types

from domain.interfaces.llm_provider import LLMProvider

load_dotenv()

_SYSTEM_INSTRUCTION = """You are a crime-data assistant. Follow the caller's language,
evidence, formatting, and output instructions exactly. Never emit application transport
markers such as <<<VETRO_CITATIONS>>> or <<<VETRO_FOLLOWUPS>>>; those are reserved for the
application server."""


class GeminiProvider(LLMProvider):
    # "gemini-flash-latest" resolves to gemini-3.5-flash, whose free-tier
    # quota is a mere 20 requests/day -- exhausted within a single
    # dev/testing session. Tried pinning to an older model
    # (gemini-2.0-flash) for a presumably friendlier quota instead, but
    # this API key's free tier has ZERO quota for it (confirmed:
    # `limit: 0` in the 429 response, not just "exhausted" -- this key's
    # free tier appears restricted to the current model generation only,
    # older generations aren't available at all, not just rate-limited).
    # "gemini-flash-lite-latest" (-> gemini-3.1-flash-lite as of this
    # writing) is confirmed reachable on this key and, being the lite
    # tier of the same generation, should carry a friendlier free quota
    # than the full-size flash model. Revisit if/when this project moves
    # to a billing-enabled key, where quota stops being the constraint.
    def __init__(self, model: str = "gemini-flash-lite-latest"):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = model
        self.generation_config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            temperature=0.2,
        )

    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        # google-genai's streaming call is sync-generator based;
        # wrap it so the route's async StreamingResponse can consume it.
        stream = self.client.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=self.generation_config,
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text

    async def generate(self, prompt: str) -> str:
        result = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=self.generation_config,
        )
        return result.text or ""
