from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class KnowledgeResult:
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "deterministic"


class KnowledgeService(Protocol):
    def query(self, topic: str, **params: Any) -> KnowledgeResult: ...
