"""LLM router — tries providers in order until one succeeds."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from .base import LLMProvider
from ..core.models import LLMResponse

logger = logging.getLogger(__name__)


class LLMRouter:
    """Routes LLM requests to providers with fallback."""

    def __init__(self, providers: list[LLMProvider]):
        self.providers = providers
        self._fallback_message = (
            "I'm sorry, I'm having trouble connecting. Please call 0343-2501353 for assistance."
        )

    @property
    def name(self) -> str:
        return self.providers[0].name if self.providers else "none"

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 384,
    ) -> LLMResponse:
        """Try providers in order until one succeeds."""
        for provider in self.providers:
            try:
                response = await provider.complete(messages, temperature, max_tokens)
                if response.content and "trouble connecting" not in response.content.lower():
                    return response
                logger.warning(f"Provider {provider.name} returned fallback response")
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue

        # All providers failed
        return LLMResponse(content=self._fallback_message, model="none")

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 384,
    ) -> AsyncIterator[str]:
        """Try providers in order for streaming."""
        for provider in self.providers:
            try:
                # Test if provider works
                async for token in provider.stream(messages, temperature, max_tokens):
                    yield token
                return
            except Exception as e:
                logger.warning(f"Provider {provider.name} stream failed: {e}")
                continue

        yield self._fallback_message
