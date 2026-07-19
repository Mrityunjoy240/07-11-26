from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class CapabilityHandler(Protocol):
    def can_handle(self, intent: str, context: dict[str, Any] | None = None) -> bool: ...

    def execute(self, context: dict[str, Any]) -> Any: ...


@dataclass
class CapabilityManifest:
    name: str
    version: str = "1.0.0"
    description: str = ""
    handler: CapabilityHandler | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._manifests: dict[str, list[CapabilityManifest]] = {}

    def register(self, manifest: CapabilityManifest) -> None:
        key = manifest.name
        if key not in self._manifests:
            self._manifests[key] = []
        self._manifests[key].append(manifest)

    def get(self, name: str, version: str | None = None) -> CapabilityManifest | None:
        versions = self._manifests.get(name)
        if not versions:
            return None
        if version:
            return next((m for m in versions if m.version == version), None)
        return versions[-1]

    def find(
        self, intent: str, context: dict[str, Any] | None = None
    ) -> list[CapabilityManifest]:
        results: list[CapabilityManifest] = []
        for versions in self._manifests.values():
            m = versions[-1]
            if m.handler and m.handler.can_handle(intent, context):
                results.append(m)
        return results

    def all(self) -> list[CapabilityManifest]:
        result: list[CapabilityManifest] = []
        for versions in self._manifests.values():
            result.append(versions[-1])
        return result

    def versions(self, name: str) -> list[str]:
        return [m.version for m in self._manifests.get(name, [])]

    def __contains__(self, name: str) -> bool:
        return name in self._manifests
