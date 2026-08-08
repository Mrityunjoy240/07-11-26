from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.fabric.runtime import AgentRuntime, TurnRequest, TurnResult
from src.fabric.tracing import SpanContext, Tracer


@dataclass(frozen=True)
class SliceResult:
    response: str
    understanding: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[str] = field(default_factory=list)
    runtime: str = ""
    trace_id: str | None = None
    latency_ms: float = 0.0
    structured_output: dict[str, Any] | None = None


class AgentSliceService:
    """Framework-neutral entry point for the vertical slice.

    Depends only on the fabric AgentRuntime protocol and the fabric tracing
    contract, so the active runtime implementation can be swapped without
    touching this class or any caller.
    """

    def __init__(
        self,
        runtime: AgentRuntime,
        *,
        tracer: Tracer | None = None,
        output_type: type | None = None,
    ) -> None:
        self._runtime = runtime
        self._tracer = tracer
        self._output_type = output_type

    async def handle(
        self,
        text: str,
        *,
        session_id: str = "",
        user_profile: dict[str, Any] | None = None,
        parent_trace: SpanContext | None = None,
        output_type: type | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SliceResult:
        request = TurnRequest(
            text=text,
            session_id=session_id,
            user_profile=user_profile or {},
            output_type=output_type or self._output_type,
            trace=parent_trace,
            metadata=metadata or {},
        )
        result: TurnResult = await self._runtime.turn(request)
        return SliceResult(
            response=result.text,
            understanding={
                "tool_calls": [tc.name for tc in result.tool_calls],
                "tool_results": [tr.name for tr in result.tool_results],
            },
            tool_calls=[tc.name for tc in result.tool_calls],
            runtime=result.runtime,
            trace_id=result.trace.trace_id if result.trace else None,
            latency_ms=float(result.metadata.get("latency_ms", 0.0)),
            structured_output=to_dict(result.structured_output),
        )


def to_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dataclass_fields__"):
        return {k: getattr(value, k) for k in vars(value)}
    return {"value": str(value)}
