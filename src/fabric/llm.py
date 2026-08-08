from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMResult:
    text: str
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(Protocol):
    provider: str
    model_name: str

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResult: ...
