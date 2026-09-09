"""Traces OpenTelemetry.

Branchées dès les fondations et non après coup : chaque étape ajoutée ensuite
hérite du contexte de trace sans travail supplémentaire. En local l'export se
fait sur la console, ce qui n'exige aucun service tiers.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_configured = False


def configure_tracing(exporter: str = "console", service_name: str = "dataguard") -> None:
    global _configured
    if _configured or exporter == "none":
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if exporter == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif exporter == "otlp":
        # Import tardif : la dépendance OTLP n'est requise que si on l'active.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured = True


def get_tracer(name: str = "dataguard") -> trace.Tracer:
    return trace.get_tracer(name)


@contextmanager
def span(name: str, **attributes: Any):
    """Ouvre un span en y attachant directement ses attributs."""
    with get_tracer().start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current
