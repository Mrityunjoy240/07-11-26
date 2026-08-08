from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from src.fabric.runtime import TurnResult


@dataclass(frozen=True)
class ValidationOutcome:
    passed: bool
    reason: str = ""
    refusal: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class TurnValidator(Protocol):
    def validate(self, result: TurnResult[Any]) -> ValidationOutcome: ...
