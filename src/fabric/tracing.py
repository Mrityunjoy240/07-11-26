from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class SpanContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


class Span(Protocol):
    @property
    def context(self) -> SpanContext: ...

    def set_attribute(self, key: str, value: Any) -> None: ...

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None: ...

    def end(self, status: str = "ok") -> None: ...

    def __enter__(self) -> Span: ...

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


class Tracer(Protocol):
    def start_span(
        self,
        name: str,
        parent: SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span: ...
