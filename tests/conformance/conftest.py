from __future__ import annotations

from src.fabric.adapters import AgentRuntimePydanticAI
from tests.conformance.registry import register_runtime

register_runtime("pydanticai", lambda: AgentRuntimePydanticAI())
