from __future__ import annotations

import ast
import pathlib

from src.fabric import runtime, tools, tracing, validation

_FORBIDDEN_IMPORTS = {"pydantic_ai", "pydantic", "langgraph", "opentelemetry"}

_FABRIC_DIR = pathlib.Path(runtime.__file__).parent


def _top_level_imports(module: str) -> set[str]:
    path = pathlib.Path(module).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.split(".")[0])
    return found


class TestContractNeutrality:
    def test_fabric_modules_do_not_import_frameworks(self):
        for path in _FABRIC_DIR.glob("*.py"):
            if path.name == "__init__.py":
                continue
            imports = _top_level_imports(str(path))
            leaks = imports & _FORBIDDEN_IMPORTS
            assert not leaks, f"{path.name} imports framework packages: {leaks}"

    def test_pydantic_ai_imports_only_in_adapters(self):
        src_root = pathlib.Path(runtime.__file__).resolve().parents[1]
        adapters_dir = (src_root / "fabric" / "adapters").resolve()
        offenders: list[str] = []
        for path in src_root.rglob("*.py"):
            if str(path.resolve()).startswith(str(adapters_dir)):
                continue
            imports = _top_level_imports(str(path))
            if "pydantic_ai" in imports:
                offenders.append(str(path.relative_to(src_root)))
        assert not offenders, f"pydantic_ai leaked outside src/fabric/adapters: {offenders}"

    def test_contract_types_are_stdlib_dataclasses(self):
        from dataclasses import is_dataclass

        assert is_dataclass(runtime.TurnRequest)
        assert is_dataclass(runtime.TurnResult)
        assert is_dataclass(runtime.TurnInterrupt)
        assert is_dataclass(tools.ToolCall)
        assert is_dataclass(tools.ToolResult)
        assert is_dataclass(tools.ToolSpec)
        assert is_dataclass(tracing.SpanContext)
        assert is_dataclass(validation.ValidationOutcome)


class TestContractSurface:
    def test_runtime_protocol_members_exist(self):
        expected = {
            "runtime_id",
            "register_tool",
            "register_validator",
            "turn",
            "stream",
        }
        assert expected <= set(runtime.AgentRuntime.__protocol_attrs__)

    def test_turn_event_union_members(self):
        for cls in (runtime.TextDelta, runtime.ToolCallStarted, runtime.ToolResultReceived, runtime.TurnFinished):
            assert issubclass(cls, object)

    def test_tool_registry_json_schema_shape(self):
        registry = tools.ToolRegistry()
        registry.register(
            tools.ToolSpec(
                name="calculate_fee",
                description="Compute fee",
                parameters={
                    "type": "object",
                    "properties": {"amount": {"type": "number"}},
                },
                handler=lambda amount: str(amount),
            )
        )
        schema = registry.json_schemas()[0]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calculate_fee"
        assert schema["function"]["parameters"]["type"] == "object"
