from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


class Engine(Protocol, Generic[InputT, OutputT]):
    def process(self, input: InputT) -> OutputT: ...


@dataclass
class UnderstandingInput:
    text: str
    state: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningInput:
    understanding: Any
    state: Any = None
    college_brain: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionInput:
    reasoning: Any
    brain_response: Any | None = None
    capabilities: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionOutput:
    action: str = ""
    priority: str = "normal"
    confidence: float = 0.0
    rationale: str = ""
    required_info: list[str] = field(default_factory=list)
    escalate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationInput:
    decision: DecisionOutput | None = None
    outcome: str = ""
    user_feedback: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationOutput:
    correct: bool = True
    confidence_adjustment: float = 0.0
    notes: str = ""
    follow_up_needed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
