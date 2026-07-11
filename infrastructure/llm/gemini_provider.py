"""
Gemini implementation of LLMProvider. This is the only file in the
whole app that imports google-genai directly -- if Gemini's SDK changes
its API shape, this is the only place that needs to change.
"""
import os
from typing import AsyncIterator

from dotenv import load_dotenv
from google import genai

from domain.interfaces.llm_provider import LLMProvider

load_dotenv()


class GeminiProvider(LLMProvider):
    # "gemini-flash-latest" is Google's floating alias to the current
    # recommended flash model -- pinning an exact version (e.g.
    # "gemini-2.5-flash") breaks silently once Google deprecates it for
    # new API keys, which is exactly what happened here.
    def __init__(self, model: str = "gemini-flash-latest"):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = model

    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        # google-genai's streaming call is sync-generator based;
        # wrap it so the route's async StreamingResponse can consume it.
        stream = self.client.models.generate_content_stream(model=self.model, contents=prompt)
        for chunk in stream:
            if chunk.text:
                yield chunk.text

    async def generate(self, prompt: str) -> str:
        result = self.client.models.generate_content(model=self.model, contents=prompt)
        return result.text or ""
