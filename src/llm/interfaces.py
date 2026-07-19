from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResponse:
    text: str
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)


class LLMAdapter(Protocol):
    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse: ...
