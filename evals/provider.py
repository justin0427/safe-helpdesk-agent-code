"""Promptfoo provider for deterministic Helpdesk security regression cases."""

import json
from pathlib import Path
import sys
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.eval_target import run_security_case


_TRACER: trace.Tracer | None = None


def _tracer() -> trace.Tracer:
    global _TRACER
    if _TRACER is None:
        provider = TracerProvider()
        provider.add_span_processor(
            SimpleSpanProcessor(
                OTLPSpanExporter(endpoint="http://127.0.0.1:4318/v1/traces")
            )
        )
        trace.set_tracer_provider(provider)
        _TRACER = trace.get_tracer("safe-helpdesk-agent.promptfoo")
    return _TRACER


def _emit_trace(result: dict[str, object], context: dict[str, Any]) -> None:
    traceparent = context.get("traceparent")
    if not isinstance(traceparent, str):
        return

    parent_context = propagate.extract({"traceparent": traceparent})
    tracer = _tracer()
    with tracer.start_as_current_span("helpdesk.agent.run", context=parent_context) as run_span:
        run_span.set_attribute("helpdesk.case", str(context["vars"]["case"]))
        for event in result.get("trace", []):
            if not isinstance(event, dict):
                continue
            name = str(event["name"])
            kind = str(event["kind"])
            with tracer.start_as_current_span(f"helpdesk.{kind}.{name}") as event_span:
                event_span.set_attribute("helpdesk.event.kind", kind)
                event_span.set_attribute("helpdesk.event.status", str(event["status"]))
                event_span.set_attribute("helpdesk.event.sequence", int(event["sequence"]))
                if kind == "tool":
                    event_span.set_attribute("tool.name", name)
                    event_span.set_attribute(
                        "tool.arguments",
                        json.dumps(event.get("data", {}), ensure_ascii=False),
                    )
    trace.get_tracer_provider().force_flush()


def call_api(prompt: str, options: dict, context: dict) -> dict:
    """Run a local safety case without calling an external model."""
    case = context["vars"]["case"]
    result = run_security_case(case)
    _emit_trace(result, context)
    return {"output": json.dumps(result, ensure_ascii=False)}
