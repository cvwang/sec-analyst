"""OpenTelemetry tracing module for agent execution and tool span instrumentation."""

import functools
import sys
from typing import Callable, Any
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from agent.config import settings


class SafeConsoleSpanExporter(ConsoleSpanExporter):
    """Console exporter that avoids writing to stdout if the stream is closed."""

    def export(self, spans):
        if sys.stdout.closed:
            return
        try:
            return super().export(spans)
        except Exception:
            pass


_provider = TracerProvider()
_processor = SimpleSpanProcessor(SafeConsoleSpanExporter())
_provider.add_span_processor(_processor)
trace.set_tracer_provider(_provider)

tracer = trace.get_tracer("sec_edgar_agent", "1.0.0")


def trace_span(name: str):
    """Decorator to trace tool functions and agent reasoning steps with OpenTelemetry spans."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(name) as span:
                span.set_attribute("gcp.project_id", settings.gcp_project_id)
                span.set_attribute("gcp.region", settings.gcp_region)
                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.StatusCode.OK)
                    return result
                except Exception as e:
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    span.record_exception(e)
                    raise e

        return wrapper

    return decorator
