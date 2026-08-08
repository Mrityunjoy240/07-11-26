from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.api.factory import build_slice_service
from src.evaluation.eval_store import JsonEvalStore
from src.fabric.adapters import AgentRuntimePydanticAI
from src.fabric.eval_store import EvalRecord
from src.fabric.runtime import TurnRequest
from src.knowledge.service import CollegeKnowledgeService
from src.knowledge.tools import build_knowledge_tools


@pytest.mark.asyncio
async def test_slice_roundtrip_with_test_model():
    service = build_slice_service(provider="testmodel")
    result = await service.handle("What is the fee for CSE?")
    assert isinstance(result.response, str)
    assert result.response
    assert result.runtime == "pydanticai"
    assert result.trace_id is None


@pytest.mark.asyncio
async def test_slice_registers_knowledge_tools():
    runtime = AgentRuntimePydanticAI()
    for tool in build_knowledge_tools(CollegeKnowledgeService()):
        runtime.register_tool(tool)
    result = await runtime.turn(TurnRequest(text="hello"))
    assert isinstance(result.text, str)
    assert result.runtime == "pydanticai"


def test_knowledge_tool_calculate_fee_is_deterministic():
    tools = build_knowledge_tools(CollegeKnowledgeService())
    names = {t.name for t in tools}
    assert {"calculate_fee", "check_eligibility", "get_scholarships"} <= names
    fee_tool = next(t for t in tools if t.name == "calculate_fee")
    out1 = fee_tool.handler(category="general")
    out2 = fee_tool.handler(category="general")
    assert out1 == out2
    assert "Tuition" in out1


def test_knowledge_tool_check_eligibility_is_deterministic():
    tools = build_knowledge_tools(CollegeKnowledgeService())
    elig = next(t for t in tools if t.name == "check_eligibility")
    out = elig.handler(rank=5000, category="general")
    assert "CSE" in out


@pytest.mark.asyncio
async def test_slice_eval_store_roundtrip(tmp_path):
    store = JsonEvalStore(tmp_path)
    store.save(
        EvalRecord(
            conversation_id="BENCH_V21_000008",
            turn_index=0,
            runtime="pydanticai",
            query="fee",
            response="Tuition: ₹85,000/year",
        )
    )
    records = store.load("BENCH_V21_000008")
    assert len(records) == 1
    assert records[0].response == "Tuition: ₹85,000/year"


@pytest.mark.asyncio
async def test_slice_structured_output_type():
    @dataclass
    class Intent:
        primary: str
        confidence: float

    service = build_slice_service(provider="testmodel", output_type=Intent)
    result = await service.handle("fee for CSE")
    assert result.structured_output is not None


@pytest.mark.asyncio
async def test_slice_otel_trace_propagates():
    from src.fabric.tracing import SpanContext
    from src.observability.otel_tracer import OTelTracer

    service = build_slice_service(provider="testmodel", tracer=OTelTracer())
    parent = SpanContext(trace_id="ab" * 16, span_id="cd" * 8)
    result = await service.handle("fee for CSE", parent_trace=parent)
    assert result.trace_id == "ab" * 16
    assert result.runtime == "pydanticai"
