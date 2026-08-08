from __future__ import annotations

from src.api.slice_service import AgentSliceService
from src.fabric.adapters import AgentRuntimePydanticAI
from src.fabric.adapters.pydanticai import PydanticAIConfig
from src.fabric.runtime import AgentRuntime
from src.fabric.tracing import Tracer
from src.knowledge.service import CollegeKnowledgeService
from src.knowledge.tools import build_knowledge_tools


def build_pydanticai_runtime(
    *,
    provider: str = "testmodel",
    model_name: str | None = None,
    api_key: str | None = None,
    tracer: Tracer | None = None,
) -> AgentRuntime:
    runtime = AgentRuntimePydanticAI(
        config=PydanticAIConfig(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
        ),
        tracer=tracer,
    )
    knowledge = CollegeKnowledgeService()
    for tool in build_knowledge_tools(knowledge):
        runtime.register_tool(tool)
    return runtime


def build_slice_service(
    *,
    provider: str = "testmodel",
    model_name: str | None = None,
    api_key: str | None = None,
    tracer: Tracer | None = None,
    output_type: type | None = None,
) -> AgentSliceService:
    runtime = build_pydanticai_runtime(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        tracer=tracer,
    )
    return AgentSliceService(runtime, tracer=tracer, output_type=output_type)
