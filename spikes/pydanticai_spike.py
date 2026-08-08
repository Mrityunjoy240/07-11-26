"""Isolated PydanticAI spike — verifies pydantic-ai==2.26.0 against the subset of
functionality required by the AgentRuntime contract (src/fabric/runtime.py).

Run with the isolated venv python from spikes/:
  .\\Scripts\\python.exe ..\\spikes\\pydanticai_spike.py

This module imports pydantic_ai at module scope ON PURPOSE. It is the isolated
compatibility probe; it is NOT part of src/fabric (which must stay framework-neutral).
"""

from __future__ import annotations

import asyncio
import sys

import pydantic_ai
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.openai import OpenAIProvider

results: list[tuple[str, str]] = []
failures: int = 0


def check(name: str, fn) -> None:
    global failures
    try:
        result = fn()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
        results.append((name, "PASS"))
    except Exception as exc:  # noqa: BLE001
        failures += 1
        results.append((name, f"FAIL: {type(exc).__name__}: {exc}"))


class Query(BaseModel):
    intent: str
    confidence: float


def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def probe_import() -> None:
    assert pydantic_ai.__version__ == "2.26.0", pydantic_ai.__version__
    assert sys.version_info[:3] == (3, 14, 4), sys.version_info


def probe_model_init() -> None:
    model = OpenAIChatModel("gpt-4o-mini", provider=OpenAIProvider(api_key="spike-noop-key"))
    assert model is not None
    test_model = TestModel()
    assert test_model is not None


def probe_groq_init() -> None:
    from pydantic_ai.models.groq import GroqModel
    from pydantic_ai.providers.groq import GroqProvider

    model = GroqModel("llama-3.3-70b-versatile", provider=GroqProvider(api_key="spike-noop"))
    assert model.model_name == "llama-3.3-70b-versatile"


async def _probe_tool_registration() -> None:
    agent = Agent(model=TestModel(), tools=[add])
    tools = agent._function_toolset.tools
    assert "add" in tools, tools
    assert "a" in tools["add"].function_schema.json_schema["properties"], tools["add"]


async def _probe_structured_output() -> None:
    agent = Agent(
        model=TestModel(custom_output_args={"intent": "fees", "confidence": 0.9}),
        output_type=Query,
    )
    result = await agent.run("what is the fee")
    assert isinstance(result.output, Query), result.output
    assert result.output.intent == "fees"
    assert result.usage.input_tokens > 0


async def _probe_streaming() -> None:
    agent = Agent(model=TestModel(custom_output_text="hello streaming"))
    async with agent.run_stream("hi") as stream:
        parts = [part async for part in stream.stream_text()]
        assert parts, "no streamed parts"


async def _probe_tool_call_with_testmodel() -> None:
    from pydantic_ai.messages import ToolReturnPart

    agent = Agent(model=TestModel(call_tools=["add"]), tools=[add])
    result = await agent.run("add 1 and 2")
    messages = result.all_messages()
    tool_returns = [
        part
        for msg in messages
        if hasattr(msg, "parts")
        for part in msg.parts
        if isinstance(part, ToolReturnPart)
    ]
    assert tool_returns, "no ToolReturnPart in message history"
    assert "add" in result.output


async def _probe_interrupt_deferred() -> None:
    from pydantic_ai import ApprovalRequired
    from pydantic_ai.messages import ToolCallPart
    from pydantic_ai.result import DeferredToolRequests

    assert issubclass(ApprovalRequired, Exception)
    assert ToolCallPart is not None
    assert DeferredToolRequests is not None


def probe_result_surface() -> None:
    from pydantic_ai import Agent, AgentRunResult

    async def _probe() -> None:
        result = await Agent(model=TestModel()).run("hi")
        assert isinstance(result, AgentRunResult)
        for required in ("output", "response", "usage", "all_messages", "new_messages"):
            assert hasattr(result, required), required

    asyncio.run(_probe())


def main() -> None:
    check("import pydantic_ai==2.26.0 on 3.14.4", probe_import)
    check("OpenAIChatModel + TestModel init", probe_model_init)
    check("GroqModel init (production LLM)", probe_groq_init)
    check("tool registration", _probe_tool_registration)
    check("structured output (pydantic model)", _probe_structured_output)
    check("streaming (stream_text)", _probe_streaming)
    check("tool call via TestModel", _probe_tool_call_with_testmodel)
    check("interrupt/deferred-tool surface", _probe_interrupt_deferred)
    check("AgentRunResult surface", probe_result_surface)

    width = max(len(n) for n, _ in results)
    print(f"\npython {sys.version.split()[0]} · pydantic-ai {pydantic_ai.__version__}")
    print("-" * (width + 14))
    for name, status in results:
        print(f"{name:<{width}}  {status}")
    print("-" * (width + 14))
    print(f"result: {'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'}")
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
