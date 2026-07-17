from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from src.config.settings import settings

tracer: trace.Tracer | None = None


def setup_tracing() -> trace.Tracer:
    global tracer
    if tracer is not None:
        return tracer

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    if settings.otel_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(__name__)
    return tracer


def get_tracer() -> trace.Tracer:
    global tracer
    if tracer is None:
        return setup_tracing()
    return tracer
