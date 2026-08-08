from __future__ import annotations

import os
from typing import Any

from src.fabric.llm import LLMProvider, LLMResult
from src.llm.groq import GroqLLM

_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class GroqLLMProvider(LLMProvider):
    provider: str = "groq"

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.model_name = model_name or _DEFAULT_MODEL
        key = api_key or os.getenv("GROQ_API_KEY", "")
        self._impl = GroqLLM(api_key=key, model=self.model_name)

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResult:
        import asyncio

        return await asyncio.to_thread(self._impl.generate, prompt, **kwargs)
