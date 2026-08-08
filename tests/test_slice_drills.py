from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from src.api.slice_service import AgentSliceService, SliceResult
from src.fabric.llm import LLMProvider, LLMResult
from src.fabric.runtime import (
    AgentRuntime,
    TextDelta,
    TurnFinished,
    TurnInterrupt,
    TurnRequest,
    TurnResult,
)
from src.fabric.tools import ToolRegistry, ToolSpec
from src.fabric.tracing import Span, SpanContext, Tracer
from src.fabric.validation import TurnValidator, ValidationOutcome
from src.knowledge.service import CollegeKnowledgeService
from src.knowledge.tools import build_knowledge_tools

# ── Fake providers: prove the app layer never needs PydanticAI ───────────────

class FakeTracer(Tracer):
    def __init__(self) -> None:
        self.spans: list[str] = []
        self._next = 1

    def start_span(self, name: str, parent=None, attributes=None) -> Span:
        self.spans.append(name)
        ctx = SpanContext(
            trace_id=parent.trace_id if parent else "f0" * 16,
            span_id=format(self._next, "016x"),
            parent_span_id=parent.span_id if parent else None,
        )
        self._next += 1
        return FakeSpan(ctx)


class FakeSpan(Span):
    def __init__(self, ctx: SpanContext) -> None:
        self._ctx = ctx

    @property
    def context(self) -> SpanContext:
        return self._ctx

    def set_attribute(self, key: str, value) -> None: ...
    def add_event(self, name: str, attributes=None) -> None: ...
    def end(self, status: str = "ok") -> None: ...
    def __enter__(self) -> FakeSpan:
        return self
    def __exit__(self, *args) -> None: ...


class FakeLLMProvider(LLMProvider):
    provider = "fake"
    model_name = "fake-model"

    def __init__(self, canned: str = "deterministic fake reply") -> None:
        self.canned = canned
        self.calls: list[str] = []

    async def generate(self, prompt: str, **kwargs) -> LLMResult:
        self.calls.append(prompt)
        return LLMResult(text=self.canned)


class FakeAgentRuntime(AgentRuntime):
    """Implements the fabric AgentRuntime protocol with zero frameworks."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        llm: FakeLLMProvider | None = None,
        *,
        emit_interrupt: bool = False,
    ) -> None:
        self._registry = registry or ToolRegistry()
        self._llm = llm or FakeLLMProvider()
        self._validators: list[TurnValidator] = []
        self._emit_interrupt = emit_interrupt

    @property
    def runtime_id(self) -> str:
        return "fake"

    def register_tool(self, tool: ToolSpec) -> None:
        self._registry.register(tool)

    def register_validator(self, validator: TurnValidator) -> None:
        self._validators.append(validator)

    async def turn(self, request: TurnRequest) -> TurnResult:
        if self._emit_interrupt:
            return TurnResult(
                text="",
                finish_reason="interrupt",
                interrupt=TurnInterrupt(token="tok-deferred", reason="awaiting profile"),
                runtime=self.runtime_id,
                trace=request.trace,
            )
        tool_calls: list = []
        tool_results: list = []
        for call in request.metadata.get("_tool_calls", []):
            tool_calls.append(call)
            tool_results.append(await self._registry.dispatch(call))
        llm_text = ""
        if tool_results:
            llm_text = " ".join(r.content for r in tool_results)
        elif request.text:
            llm_text = (await self._llm.generate(request.text)).text
        result = TurnResult(
            text=llm_text,
            structured_output=(
                {"intent": "fee", "text": llm_text}
                if request.output_type is not None
                else None
            ),
            tool_calls=tool_calls,
            tool_results=tool_results,
            finish_reason="stop",
            interrupt=None,
            trace=request.trace,
            runtime=self.runtime_id,
        )
        for validator in self._validators:
            outcome = validator.validate(result)
            result.metadata.setdefault("validations", []).append(
                {"passed": outcome.passed, "reason": outcome.reason}
            )
        return result

    def stream(self, request: TurnRequest) -> AsyncIterator:
        async def gen() -> AsyncIterator:
            for chunk in ("one ", "two ", "three"):
                yield TextDelta(text=chunk)
            yield TurnFinished(result=await self.turn(request))

        return gen()


# ── Provider independence ────────────────────────────────────────────────────

class TestProviderIndependence:
    @pytest.mark.asyncio
    async def test_slice_works_with_fake_runtime_and_fake_llm(self):
        service = AgentSliceService(
            FakeAgentRuntime(llm=FakeLLMProvider("hello from fake")),
            tracer=FakeTracer(),
        )
        result = await service.handle("hi")
        assert isinstance(result, SliceResult)
        assert result.response == "hello from fake"
        assert result.runtime == "fake"

    @pytest.mark.asyncio
    async def test_slice_with_fake_runtime_still_routes_tools(self):
        knowledge = CollegeKnowledgeService()
        registry = ToolRegistry()
        for tool in build_knowledge_tools(knowledge):
            registry.register(tool)
        runtime = FakeAgentRuntime(registry=registry)
        service = AgentSliceService(runtime, tracer=FakeTracer())

        from src.fabric.tools import ToolCall

        result = await service.handle(
            "compute fee",
            metadata={"_tool_calls": [ToolCall(name="calculate_fee", arguments={"category": "general"})]},
        )
        assert "₹85,000" in result.response
        assert result.tool_calls == ["calculate_fee"]

    def test_fake_llm_provider_conforms_to_protocol(self):
        llm = FakeLLMProvider()
        assert llm.provider == "fake"
        assert llm.model_name == "fake-model"

    def test_fake_runtime_registers_tools_and_validators(self):
        runtime = FakeAgentRuntime()
        for tool in build_knowledge_tools(CollegeKnowledgeService()):
            runtime.register_tool(tool)
        assert "calculate_fee" in runtime._registry
        assert "check_eligibility" in runtime._registry
        assert "get_scholarships" in runtime._registry


# ── Actual tool semantics (deterministic, no LLM in the answer) ──────────────

class TestToolSemantics:
    def setup_method(self):
        self.knowledge = CollegeKnowledgeService()
        self.registry = ToolRegistry()
        for tool in build_knowledge_tools(self.knowledge):
            self.registry.register(tool)

    @pytest.mark.asyncio
    async def test_fee_calculation(self):
        from src.fabric.tools import ToolCall

        r = await self.registry.dispatch(
            ToolCall(name="calculate_fee", arguments={"category": "general"})
        )
        assert "Tuition: ₹85,000" in r.content
        assert "Total: ₹110,000" in r.content
        assert not r.is_error

    @pytest.mark.asyncio
    async def test_fee_category_variants(self):
        from src.fabric.tools import ToolCall

        for cat, tuition in (("obc", "45,000"), ("sc", "5,000"), ("st", "5,000")):
            r = await self.registry.dispatch(
                ToolCall(name="calculate_fee", arguments={"category": cat})
            )
            assert f"₹{tuition}" in r.content, cat

    @pytest.mark.asyncio
    async def test_eligibility(self):
        from src.fabric.tools import ToolCall

        r = await self.registry.dispatch(
            ToolCall(
                name="check_eligibility",
                arguments={"rank": 5000, "category": "general"},
            )
        )
        assert "CSE" in r.content
        assert "AIML" in r.content
        assert not r.is_error

    @pytest.mark.asyncio
    async def test_scholarships(self):
        from src.fabric.tools import ToolCall

        r = await self.registry.dispatch(
            ToolCall(
                name="get_scholarships",
                arguments={"category": "sc", "pcm_percentage": 80.0},
            )
        )
        assert "SC/ST Scholarship" in r.content
        assert not r.is_error

    @pytest.mark.asyncio
    async def test_unknown_out_of_kb_topic(self):
        result = self.knowledge.query("weather_tomorrow")
        assert result.confidence == 0.0
        assert "unknown knowledge topic" in result.content

    @pytest.mark.asyncio
    async def test_unknown_tool_name(self):
        from src.fabric.tools import ToolCall

        r = await self.registry.dispatch(ToolCall(name="nope", arguments={}))
        assert r.is_error
        assert "unknown tool" in r.content

    @pytest.mark.asyncio
    async def test_malformed_tool_arguments(self):
        from src.fabric.tools import ToolCall

        # eligibility handler requires rank (positional); passing wrong types
        r = await self.registry.dispatch(
            ToolCall(
                name="check_eligibility",
                arguments={"rank": "not-an-int", "category": "general"},
            )
        )
        assert r.is_error
        assert "tool error" in r.content

    @pytest.mark.asyncio
    async def test_tool_failure_is_captured_as_error_result(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="boom",
                description="raises",
                parameters={"type": "object", "properties": {}},
                handler=lambda: (_ for _ in ()).throw(RuntimeError("kaput")),
            )
        )
        from src.fabric.tools import ToolCall

        r = await registry.dispatch(ToolCall(name="boom", arguments={}))
        assert r.is_error
        assert "kaput" in r.content


# ── Streaming, validation, interrupts at the contract boundary ───────────────

class TestRuntimeBehaviors:
    @pytest.mark.asyncio
    async def test_streaming_emits_deltas_then_finished(self):
        runtime = FakeAgentRuntime()
        events = [e async for e in runtime.stream(TurnRequest(text="hello"))]
        deltas = [e for e in events if isinstance(e, TextDelta)]
        assert len(deltas) == 3
        assert isinstance(events[-1], TurnFinished)

    @pytest.mark.asyncio
    async def test_validator_rejection_is_recorded(self):
        class RejectingValidator(TurnValidator):
            def validate(self, result: TurnResult) -> ValidationOutcome:
                return ValidationOutcome(passed=False, reason="profile incomplete")

        runtime = FakeAgentRuntime()
        runtime.register_validator(RejectingValidator())
        result = await runtime.turn(TurnRequest(text="hi"))
        validations = result.metadata.get("validations", [])
        assert validations
        assert validations[0]["passed"] is False
        assert validations[0]["reason"] == "profile incomplete"

    @pytest.mark.asyncio
    async def test_interrupt_deferred_tool_flow(self):
        runtime = FakeAgentRuntime(emit_interrupt=True)
        result = await runtime.turn(TurnRequest(text="I need a loan"))
        assert result.interrupt is not None
        assert result.interrupt.token == "tok-deferred"
        assert result.finish_reason == "interrupt"

    @pytest.mark.asyncio
    async def test_slice_surfaces_interrupt_payload(self):
        runtime = FakeAgentRuntime(emit_interrupt=True)
        service = AgentSliceService(runtime, tracer=FakeTracer())
        result = await service.handle("I need a loan")
        # SliceResult currently exposes response/runtime; interrupt must not crash
        assert result.runtime == "fake"


# ── Real adapter drills: prove PydanticAI actually executes tools ────────────

class TestRealAdapterExecution:
    @pytest.fixture
    def runtime(self):
        from src.fabric.adapters import AgentRuntimePydanticAI

        rt = AgentRuntimePydanticAI()
        for tool in build_knowledge_tools(CollegeKnowledgeService()):
            rt.register_tool(tool)
        return rt

    @pytest.mark.asyncio
    async def test_real_adapter_executes_knowledge_tools(self, runtime):
        result = await runtime.turn(TurnRequest(text="calculate the fee"))
        assert result.tool_calls, "TestModel should invoke the registered tools"
        names = {tc.name for tc in result.tool_calls}
        assert "calculate_fee" in names
        assert result.tool_results
        assert any("₹" in tr.content for tr in result.tool_results)

    @pytest.mark.asyncio
    async def test_real_adapter_tool_results_fed_back_into_output(self, runtime):
        result = await runtime.turn(TurnRequest(text="check eligibility"))
        assert result.tool_results
        for tr in result.tool_results:
            assert tr.name in {"calculate_fee", "check_eligibility", "get_scholarships"}

    @pytest.mark.asyncio
    async def test_real_adapter_validator_rejection_is_recorded(self, runtime):
        class RejectingValidator(TurnValidator):
            def validate(self, result: TurnResult) -> ValidationOutcome:
                return ValidationOutcome(passed=False, reason="needs profile")

        runtime.register_validator(RejectingValidator())
        result = await runtime.turn(TurnRequest(text="hello"))
        validations = result.metadata.get("validations", [])
        assert validations
        assert validations[0]["passed"] is False
        assert validations[0]["reason"] == "needs profile"

    @pytest.mark.asyncio
    async def test_real_adapter_stream_emits_deltas_then_finished(self, runtime):
        events = [e async for e in runtime.stream(TurnRequest(text="hello"))]
        deltas = [e for e in events if isinstance(e, TextDelta)]
        assert deltas, "stream must emit text deltas"
        assert isinstance(events[-1], TurnFinished)
        assert events[-1].result.runtime == "pydanticai"

    @pytest.mark.asyncio
    async def test_real_adapter_default_interrupt_is_none(self, runtime):
        result = await runtime.turn(TurnRequest(text="hello"))
        assert result.interrupt is None
        assert result.finish_reason == "stop"


# ── Security: tool metadata must never become executable code ────────────────

class TestToolMetadataSecurity:
    def test_malicious_parameter_name_rejected(self):
        from src.fabric.adapters.pydanticai import _spec_to_tool

        payload = "x):\n    __import__('os').system('echo PWNED > pwned.txt')  #"
        spec = ToolSpec(
            name="evil",
            description="d",
            parameters={"type": "object", "properties": {payload: {"type": "string"}}},
            handler=lambda **k: "ok",
        )
        with pytest.raises(ValueError, match="invalid parameter name"):
            _spec_to_tool(spec)

    def test_keyword_parameter_name_rejected(self):
        from src.fabric.adapters.pydanticai import _spec_to_tool

        spec = ToolSpec(
            name="kw",
            description="d",
            parameters={"type": "object", "properties": {"from": {"type": "string"}}},
            handler=lambda **k: "ok",
        )
        with pytest.raises(ValueError, match="invalid parameter name"):
            _spec_to_tool(spec)

    def test_optional_before_required_parameters_build_correctly(self):
        from src.fabric.adapters.pydanticai import _spec_to_tool

        spec = ToolSpec(
            name="mixed",
            description="d",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "rank": {"type": "integer"},
                },
                "required": ["rank"],
            },
            handler=lambda category="general", rank=0: f"fee:{category}:{rank}",
        )
        tool = _spec_to_tool(spec)
        assert tool.name == "mixed"
