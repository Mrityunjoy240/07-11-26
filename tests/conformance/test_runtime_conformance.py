from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.fabric.runtime import (
    AgentRuntime,
    TurnFinished,
    TurnInterrupt,
    TurnRequest,
    TurnResult,
)
from src.fabric.tools import ToolSpec
from src.fabric.tracing import SpanContext
from src.fabric.validation import TurnValidator, ValidationOutcome
from tests.conformance.registry import runtime_under_test


def _echo_spec() -> ToolSpec:
    return ToolSpec(
        name="echo",
        description="Echo text back",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=lambda text: f"echo:{text}",
        deterministic=True,
    )


@pytest.fixture(scope="module")
def runtime() -> tuple[str, AgentRuntime]:
    under_test = runtime_under_test()
    if under_test is None:
        pytest.skip("no AgentRuntime implementation registered for conformance")
    return under_test


class TestTurnContract:
    @pytest.mark.asyncio
    async def test_turn_returns_turn_result(self, runtime):
        name, rt = runtime
        result = await rt.turn(TurnRequest(text="hello"))
        assert isinstance(result, TurnResult)
        assert isinstance(result.text, str)
        assert result.runtime == name

    @pytest.mark.asyncio
    async def test_turn_accepts_span_context(self, runtime):
        _, rt = runtime
        trace = SpanContext(trace_id="abc", span_id="def")
        result = await rt.turn(TurnRequest(text="hi", trace=trace))
        assert isinstance(result, TurnResult)


class TestStructuredOutput:
    @dataclass
    class Query:
        intent: str
        confidence: float

    @pytest.mark.asyncio
    async def test_structured_output_returns_turn_result(self, runtime):
        _, rt = runtime
        result = await rt.turn(
            TurnRequest(text="what is the fee for CSE", output_type=self.Query)
        )
        assert isinstance(result, TurnResult)


class TestStreaming:
    @pytest.mark.asyncio
    async def test_stream_emits_events_and_terminates(self, runtime):
        _, rt = runtime
        events = [e async for e in rt.stream(TurnRequest(text="hello"))]
        assert events, "stream must emit at least one event"
        assert isinstance(events[-1], TurnFinished)


class TestRegistration:
    @pytest.mark.asyncio
    async def test_register_tool_and_validator(self, runtime):
        _, rt = runtime

        class AlwaysPass(TurnValidator):
            def validate(self, result: TurnResult) -> ValidationOutcome:
                return ValidationOutcome(passed=True)

        rt.register_tool(_echo_spec())
        rt.register_validator(AlwaysPass())

        result = await rt.turn(TurnRequest(text="hello"))
        assert isinstance(result, TurnResult)


class TestInterruptResume:
    def test_interrupt_token_shape(self):
        interrupt = TurnInterrupt(token="tok-1", reason="awaiting input", payload={"q": 1})
        assert interrupt.token == "tok-1"
        assert interrupt.reason == "awaiting input"
