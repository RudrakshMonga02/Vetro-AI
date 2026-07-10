"""
Factory that decides which LLMProvider implementation to hand out,
based on the LLM_BACKEND env var. This is the one place in the whole
app that knows which providers exist -- ChatService (and later,
agent/investigation use-cases) just call get_llm_provider() and use
the returned object through the LLMProvider interface, never caring
which backend is actually live.

Usage:
    LLM_BACKEND=gemini            -> GeminiProvider (current default)
    LLM_BACKEND=catalyst_quickml  -> CatalystQuickMLProvider (not yet implemented)

Adding a new provider (OpenAI, Claude, a local model, etc.) means:
  1. Write infrastructure/llm/<new>_provider.py implementing LLMProvider
  2. Add one line here
No other file in the app needs to change.
"""
import os

from domain.interfaces.llm_provider import LLMProvider


def get_llm_provider() -> LLMProvider:
    backend = os.getenv("LLM_BACKEND", "gemini").lower()

    if backend == "gemini":
        from infrastructure.llm.gemini_provider import GeminiProvider
        return GeminiProvider()

    if backend == "catalyst_quickml":
        from infrastructure.llm.catalyst_quickml_provider import CatalystQuickMLProvider
        return CatalystQuickMLProvider()

    raise ValueError(f"Unknown LLM_BACKEND: {backend!r} (expected 'gemini' or 'catalyst_quickml')")
