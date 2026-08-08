from __future__ import annotations

import inspect
import keyword
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.tools import Tool

from src.fabric.runtime import (
    TextDelta,
    TurnFinished,
    TurnRequest,
    TurnResult,
)
from src.fabric.tools import ToolCall, ToolResult, ToolSpec
from src.fabric.tracing import SpanContext, Tracer
from src.fabric.validation import TurnValidator

_JSON_TO_PY = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "object": "dict",
    "array": "list",
}


@dataclass
class PydanticAIConfig:
    provider: str = "testmodel"
    model_name: str | None = None
    api_key: str | None = None
    max_retries: int = 2
    model_settings: dict[str, Any] = field(default_factory=dict)


def _spec_to_tool(spec: ToolSpec) -> Tool:
    """Translate a framework-neutral ToolSpec into a pydantic_ai Tool.

    The tool schema is generated natively by pydantic-ai from a dynamically
    built wrapper whose signature mirrors the ToolSpec JSON Schema, so tool
    calls are validated by the framework and delivered as plain kwargs.
    """

    def wrapped(**kwargs: Any) -> str:
        value = spec.handler(**kwargs)
        if inspect.isawaitable(value):
            raise RuntimeError("async tool handlers not supported by pydantic-ai adapter")
        return str(value)

    properties = spec.parameters.get("properties", {})
    required = set(spec.parameters.get("required", []))
    sig_parts: list[str] = []
    call_parts: list[str] = []
    for pname, pmeta in properties.items():
        if not pname.isidentifier() or keyword.iskeyword(pname):
            raise ValueError(
                f"tool '{spec.name}' has invalid parameter name: {pname!r}"
            )
        pytype = _JSON_TO_PY.get(pmeta.get("type", "string"), "str")
        default = "" if pname in required else " = None"
        sig_parts.append(f"{pname}: {pytype}{default}")
        call_parts.append(f"{pname}={pname}")
    # Python requires parameters without defaults to precede those with
    # defaults, so order required parameters before optional ones.
    ordered = sorted(
        zip(sig_parts, call_parts, strict=False),
        key=lambda pair: pair[0].split(":", 1)[0] not in required,
    )
    sig_parts = [s for s, _ in ordered]
    call_parts = [c for _, c in ordered]
    call_args = ", ".join(call_parts)

    body = (
        f"def _tool_fn({', '.join(sig_parts)}):\n"
        f"    return _wrapped({call_args})\n"
    )
    ns: dict[str, Any] = {"_wrapped": wrapped}
    exec(compile(body, f"<tool:{spec.name}>", "exec"), ns)  # noqa: S102
    return Tool(ns["_tool_fn"], name=spec.name, description=spec.description, takes_ctx=False)


class AgentRuntimePydanticAI:
    """AgentRuntime adapter backed by pydantic-ai (>=2.26).

    This is the only module that imports pydantic-ai. Everything crossing the
    boundary is translated to the framework-neutral fabric contracts.
    """

    def __init__(
        self,
        *,
        config: PydanticAIConfig | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self._config = config or PydanticAIConfig()
        self._tracer = tracer
        self._tool_specs: list[ToolSpec] = []
        self._validators: list[TurnValidator] = []
        self._model = None
        self._agent = None
        self._agent_output_type: type | None = None
        self._usage: dict[str, int] = {}

    @property
    def runtime_id(self) -> str:
        return "pydanticai"

    def register_tool(self, tool: ToolSpec) -> None:
        self._tool_specs.append(tool)
        self._agent = None

    def register_validator(self, validator: TurnValidator) -> None:
        self._validators.append(validator)

    def _build_model(self):
        if self._model is not None:
            return self._model
        cfg = self._config
        if cfg.provider == "testmodel":
            self._model = TestModel()
        elif cfg.provider == "groq":
            from pydantic_ai.models.groq import GroqModel
            from pydantic_ai.providers.groq import GroqProvider

            self._model = GroqModel(
                cfg.model_name or "llama-3.3-70b-versatile",
                provider=GroqProvider(api_key=cfg.api_key),
            )
        elif cfg.provider == "openai":
            self._model = OpenAIChatModel(
                cfg.model_name or "gpt-4o-mini",
                provider=OpenAIProvider(api_key=cfg.api_key),
            )
        else:
            raise ValueError(f"unsupported provider: {cfg.provider}")
        return self._model

    def _build_agent(self, output_type: type | None):
        if self._agent is not None and self._agent_output_type is output_type:
            return self._agent
        tools = [_spec_to_tool(s) for s in self._tool_specs]
        kwargs: dict[str, Any] = {
            "model": self._build_model(),
            "tools": tools,
            "retries": self._config.max_retries,
            "model_settings": self._config.model_settings,
        }
        if output_type is not None:
            kwargs["output_type"] = output_type
        self._agent_output_type = output_type
        self._agent = Agent(**kwargs)
        return self._agent

    async def turn(self, request: TurnRequest[Any]) -> TurnResult[Any]:
        span = None
        if self._tracer is not None:
            span = self._tracer.start_span("agent.turn", parent=request.trace)
        try:
            agent = self._build_agent(request.output_type)
            result = await agent.run(request.text)
            return await self._to_turn_result(request, result, span)
        except Exception:
            if span is not None:
                span.end("error")
            raise

    async def _to_turn_result(self, request: TurnRequest, result, span, stream=None):
        tool_calls, tool_results = self._extract_tools(stream or result)
        output = getattr(result, "output", None)
        if output is None:
            output = result
        text = str(output)
        usage = self._usage_from(stream or result)
        trace = self._span_context(span, request.trace)
        turn_result = TurnResult(
            text=text,
            structured_output=output if request.output_type is not None else None,
            tool_calls=tool_calls,
            tool_results=tool_results,
            finish_reason="stop",
            interrupt=None,
            trace=trace,
            runtime=self.runtime_id,
            usage=usage,
        )
        for validator in self._validators:
            outcome = validator.validate(turn_result)
            turn_result.metadata.setdefault("validations", []).append(
                {"passed": outcome.passed, "reason": outcome.reason}
            )
        if span is not None:
            span.set_attribute("fabric.tool_calls", len(tool_calls))
            span.end("ok")
        return turn_result

    async def stream(self, request: TurnRequest[Any]) -> AsyncIterator:
        span = None
        if self._tracer is not None:
            span = self._tracer.start_span("agent.stream", parent=request.trace)
        agent = self._build_agent(request.output_type)
        async with agent.run_stream(request.text) as stream:
            async for delta in stream.stream_text():
                yield TextDelta(text=delta)
            streamed = await stream.get_output()
            result = await self._to_turn_result(request, streamed, span, stream=stream)
        yield TurnFinished(result=result)

    def _extract_tools(self, result) -> tuple[list[ToolCall], list[ToolResult]]:
        tool_calls: list[ToolCall] = []
        tool_results: list[ToolResult] = []
        all_messages = getattr(result, "all_messages", None)
        if all_messages is None:
            return tool_calls, tool_results
        messages = all_messages()
        if isinstance(messages, (list, tuple)):
            pass
        elif hasattr(messages, "await"):
            raise RuntimeError("all_messages returned awaitable")
        for message in messages:
            for part in getattr(message, "parts", []):
                part_name = type(part).__name__
                if part_name == "ToolCallPart":
                    tool_calls.append(
                        ToolCall(
                            name=getattr(part, "tool_name", ""),
                            arguments=getattr(part, "args", {}),
                            call_id=getattr(part, "part_id", ""),
                        )
                    )
                elif part_name == "ToolReturnPart":
                    tool_results.append(
                        ToolResult(
                            name=getattr(part, "tool_name", ""),
                            content=str(getattr(part, "content", "")),
                            call_id=getattr(part, "part_id", ""),
                        )
                    )
        return tool_calls, tool_results

    def _usage_from(self, result) -> dict[str, int]:
        usage = getattr(result, "usage", None)
        if usage is None:
            return dict(self._usage)
        values = {
            "input_tokens": getattr(usage, "input_tokens", 0),
            "output_tokens": getattr(usage, "output_tokens", 0),
            "requests": getattr(usage, "requests", 0),
        }
        self._usage = {k: int(v) for k, v in values.items()}
        return dict(self._usage)

    def _span_context(self, span, request_trace: SpanContext | None) -> SpanContext | None:
        if span is not None:
            try:
                return span.context
            except Exception:
                return request_trace
        return request_trace
