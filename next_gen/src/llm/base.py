"""LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from ..core.models import LLMResponse


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 384,
    ) -> LLMResponse:
        """Generate a complete response."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 384,
    ) -> AsyncIterator[str]:
        """Stream tokens one by one."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...
