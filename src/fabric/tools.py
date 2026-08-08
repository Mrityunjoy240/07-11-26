from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""


@dataclass(frozen=True)
class ToolResult:
    name: str
    content: str
    is_error: bool = False
    call_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


ToolHandler = Callable[..., ToolResult | Awaitable[ToolResult]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    deterministic: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolRegistry:
    _tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def json_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._tools.values()
        ]

    async def dispatch(self, call: ToolCall) -> ToolResult:
        spec = self._tools.get(call.name)
        if spec is None:
            return ToolResult(
                name=call.name,
                content=f"unknown tool: {call.name}",
                is_error=True,
                call_id=call.call_id,
            )
        try:
            value = spec.handler(**call.arguments)
            if inspect.isawaitable(value):
                value = await value
            if isinstance(value, ToolResult):
                return value
            return ToolResult(name=call.name, content=str(value), call_id=call.call_id)
        except Exception as exc:  # noqa: BLE001 - tool boundary converts to result
            return ToolResult(
                name=call.name,
                content=f"tool error: {exc}",
                is_error=True,
                call_id=call.call_id,
            )

    def __contains__(self, name: str) -> bool:
        return name in self._tools
