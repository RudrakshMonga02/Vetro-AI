"""
LLMProvider interface -- domain layer, zero external dependencies.
This is the seam that lets ChatService (and later, agent/investigation
use-cases) work against any text-generation backend without importing
google-genai, the Catalyst SDK, openai, or anything else directly:

  - Gemini              -> infrastructure/llm/gemini_provider.py
  - Catalyst QuickML     -> infrastructure/llm/catalyst_quickml_provider.py
  - OpenAI (future)       -> infrastructure/llm/openai_provider.py
  - any future provider   -> new file in infrastructure/llm/, same interface

Application code must only ever depend on this interface. Swapping
providers means swapping which implementation the factory constructs
(infrastructure/llm/llm_factory.py), never touching calling code.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        """Yield text chunks as they're generated."""
        ...
