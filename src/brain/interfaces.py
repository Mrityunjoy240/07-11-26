from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Reason:
    condition: str
    met: bool
    detail: str = ""


@dataclass
class BrainQuery:
    rank: int | float | None = None
    pcm_percentage: float | None = None
    category: str = "general"
    board: str = ""
    interest: str = ""
    budget: float | None = None
    location: str = ""


@dataclass
class BrainResponse:
    admission: Any = None
    placement: Any = None
    fees: Any = None
    hostel: Any = None
    scholarship: Any = None
    confidence: float = 0.0


@dataclass
class PolicyResult:
    applicable: bool = False
    details: str = ""
    confidence: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)
    why: list[Reason] = field(default_factory=list)


class Policy(Protocol):
    def evaluate(self, query: BrainQuery) -> PolicyResult: ...
