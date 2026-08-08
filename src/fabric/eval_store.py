from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class EvalRecord:
    conversation_id: str
    turn_index: int
    runtime: str
    query: str
    response: str
    structured_output: dict[str, Any] | None = None
    tool_calls: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    checks_passed: int = 0
    checks_total: int = 0
    score: float = 0.0
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EvalStore(Protocol):
    def save(self, record: EvalRecord) -> None: ...

    def load(self, conversation_id: str) -> list[EvalRecord]: ...
