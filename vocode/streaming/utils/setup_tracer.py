# vocode/streaming/utils/setup_tracer.py

import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, Status, StatusCode

tracer = trace.get_tracer(__name__)


def setup_tracer():
    """
    Setup the tracer for the application based on the environment.
    Environment variable ENV should be set to "prod" for production environment and "dev" for development environment.
    """
    try:
        tracer_provider = TracerProvider()
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "default_project_id")
        cloud_trace_exporter = CloudTraceSpanExporter(project_id=project_id)
        if os.getenv("ENV") == "prod":
            tracer_provider.add_span_processor(BatchSpanProcessor(cloud_trace_exporter))
            trace.set_tracer_provider(tracer_provider)
        return trace.get_tracer(__name__)
    except Exception as e:
        print(f"Failed to setup tracer: {str(e)}")
        return trace.get_tracer(__name__)


def span_event(span: Span, event_name: str, event_data: dict):
    if span is None:
        return
    if span.is_recording():
        span.add_event(event_name, event_data)


def start_span_in_ctx(
    name: str,
    parent_span: Span,
    attributes: Optional[dict] = None,
):
    if parent_span is None:
        return None
    elif not parent_span.is_recording():
        return None
    else:
        ctx = trace.set_span_in_context(parent_span)
        return tracer.start_span(
            name=name,
            context=ctx,
            attributes=attributes,
        )


def end_span(span: Span):
    if span is None:
        return
    if span.is_recording():
        span.end()
