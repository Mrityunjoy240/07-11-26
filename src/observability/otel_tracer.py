from __future__ import annotations

from typing import Any

from opentelemetry import trace

from src.fabric.tracing import Span, SpanContext, Tracer


class OTelSpan(Span):
    def __init__(self, span: trace.Span) -> None:
        self._span = span
        self._context = None

    @property
    def context(self) -> SpanContext:
        if self._context is None:
            ctx = self._span.get_span_context()
            attrs = dict(getattr(self._span, "attributes", None) or {})
            self._context = SpanContext(
                trace_id=format(ctx.trace_id, "032x"),
                span_id=format(ctx.span_id, "016x"),
                attributes=attrs,
            )
        return self._context

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self._span.add_event(name, attributes or {})

    def end(self, status: str = "ok") -> None:
        if status == "ok":
            self._span.set_status(trace.StatusCode.OK)
        else:
            self._span.set_status(trace.StatusCode.ERROR, description=status)
        self._span.end()


def _from_span_context(parent: SpanContext | None) -> trace.SpanContext | None:
    if parent is None:
        return None
    try:
        return trace.SpanContext(
            trace_id=int(parent.trace_id, 16),
            span_id=int(parent.span_id, 16),
            is_remote=False,
        )
    except ValueError:
        return None


class OTelTracer(Tracer):
    """Adapter between the framework-neutral fabric Tracer contract and
    OpenTelemetry. Runs entirely in the application layer; the fabric contract
    never imports opentelemetry."""

    def __init__(self, tracer: trace.Tracer | None = None) -> None:
        from src.observability.tracing import get_tracer

        self._tracer = tracer or get_tracer()

    def start_span(
        self,
        name: str,
        parent: SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        parent_ctx = _from_span_context(parent)
        context = None
        if parent_ctx is not None:
            context = trace.set_span_in_context(trace.NonRecordingSpan(parent_ctx))
        with self._tracer.start_as_current_span(
            name,
            context=context,
        ) as span:
            for key, value in (attributes or {}).items():
                span.set_attribute(key, value)
            return OTelSpan(span)
