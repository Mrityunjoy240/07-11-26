from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Turn:
    speaker: str = "assistant"
    action: str = ""
    content: str = ""
    expected_input: str = ""
    confidence: float = 0.0


@dataclass
class Plan:
    turns: list[Turn] = field(default_factory=list)
    confidence: float = 0.0
    escalate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
