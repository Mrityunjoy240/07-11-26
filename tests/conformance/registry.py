from __future__ import annotations

from collections.abc import Callable

from src.fabric.runtime import AgentRuntime

RuntimeFactory = Callable[[], AgentRuntime]

_registry: list[tuple[str, RuntimeFactory]] = []


def register_runtime(name: str, factory: RuntimeFactory) -> None:
    _registry.append((name, factory))


def registered_runtimes() -> list[tuple[str, RuntimeFactory]]:
    return list(_registry)


def runtime_under_test() -> tuple[str, AgentRuntime] | None:
    if not _registry:
        return None
    name, factory = _registry[0]
    return name, factory()
