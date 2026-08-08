from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar, runtime_checkable

from src.fabric.tools import ToolCall, ToolResult, ToolSpec
from src.fabric.tracing import SpanContext

if TYPE_CHECKING:
    from src.fabric.validation import TurnValidator

T = TypeVar("T")


@dataclass(frozen=True)
class TurnRequest(Generic[T]):
    text: str
    session_id: str = ""
    user_profile: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    output_type: type[T] | None = None
    trace: SpanContext | None = None
    resume_token: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TurnInterrupt:
    token: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TurnResult(Generic[T]):
    text: str
    structured_output: T | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    finish_reason: str = "stop"
    citations: list[str] = field(default_factory=list)
    interrupt: TurnInterrupt | None = None
    trace: SpanContext | None = None
    runtime: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCallStarted:
    call: ToolCall


@dataclass(frozen=True)
class ToolResultReceived:
    result: ToolResult


@dataclass(frozen=True)
class StructuredOutputReady:
    value: Any


@dataclass(frozen=True)
class TurnFinished:
    result: TurnResult[Any]


TurnEvent = TextDelta | ToolCallStarted | ToolResultReceived | StructuredOutputReady | TurnFinished


@runtime_checkable
class AgentRuntime(Protocol):
    @property
    def runtime_id(self) -> str: ...

    def register_tool(self, tool: ToolSpec) -> None: ...

    def register_validator(self, validator: TurnValidator) -> None: ...

    async def turn(self, request: TurnRequest[Any]) -> TurnResult[Any]: ...

    def stream(self, request: TurnRequest[Any]) -> AsyncIterator[TurnEvent]: ...
