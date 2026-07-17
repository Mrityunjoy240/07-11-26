"""Groq LLM provider — free, fast inference."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import AsyncIterator

from .base import LLMProvider
from ..core.models import LLMResponse

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """Groq API provider using llama-3.1-8b-instant."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = "llama-3.1-8b-instant"
        self._client = None
        self._async_client = None

    def _init_client(self):
        """Lazy-initialize the Groq client."""
        if self._client is not None:
            return

        try:
            from groq import Groq, AsyncGroq
            self._client = Groq(api_key=self.api_key)
            self._async_client = AsyncGroq(api_key=self.api_key)
            logger.info("Groq client initialized")
        except ImportError:
            logger.error("groq package not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            raise

    @property
    def name(self) -> str:
        return "groq"

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 384,
    ) -> LLMResponse:
        """Generate a complete response from Groq."""
        self._init_client()
        start = time.time()

        try:
            completion = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.chat.completions.create,
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=10.0,
            )
            content = (completion.choices[0].message.content or "").strip()
            latency_ms = int((time.time() - start) * 1000)

            return LLMResponse(
                content=content,
                model=self.model,
                tokens_used=completion.usage.total_tokens if completion.usage else 0,
                latency_ms=latency_ms,
                finish_reason=completion.choices[0].finish_reason or "",
            )
        except asyncio.TimeoutError:
            logger.warning("Groq API timeout")
            return LLMResponse(content="I'm having trouble connecting. Please try again.", model=self.model)
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return LLMResponse(content="I'm having trouble connecting. Please try again.", model=self.model)

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 384,
    ) -> AsyncIterator[str]:
        """Stream tokens from Groq."""
        self._init_client()

        try:
            stream = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Groq stream error: {e}")
            yield "I'm having trouble connecting. Please try again."
