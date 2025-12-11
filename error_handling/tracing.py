"""
OpenTelemetry configuration and utilities for distributed tracing.
"""
import os
from typing import Optional, Dict, Any
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, DEPLOYMENT_ENVIRONMENT
from opentelemetry.trace.status import Status, StatusCode

def setup_tracing(
    service_name: str = "kyc-orchestrator",
    environment: str = "development",
    otlp_endpoint: Optional[str] = None,
    service_version: str = "1.0.0",
) -> None:
    """
    Configure OpenTelemetry tracing for the application.
    
    Args:
        service_name: Name of the service for tracing
        environment: Deployment environment (e.g., 'development', 'production')
        otlp_endpoint: OTLP endpoint URL (e.g., 'http://localhost:4317')
        service_version: Version of the service
    """
    # Use environment variables if not provided
    otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    
    # Configure resource
    resource = Resource.create({
        SERVICE_NAME: service_name,
        DEPLOYMENT_ENVIRONMENT: environment,
        "service.version": service_version,
    })
    
    # Configure provider
    provider = TracerProvider(resource=resource)
    
    # Add console exporter in development for local debugging (but skip during tests)
    import sys
    is_test = 'pytest' in sys.modules or 'unittest' in sys.modules
    
    if environment == "development" and not is_test:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(
            BatchSpanProcessor(console_exporter)
        )
    
    # Add OTLP exporter if configured
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
    
    # Set the global tracer provider
    trace.set_tracer_provider(provider)
    
    # Configure global tracer
    tracer = trace.get_tracer(service_name, service_version)
    
    return tracer

def instrument_fastapi(app):
    """Instrument a FastAPI application for tracing."""
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    return app

def get_tracer(name: str = None) -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name or __name__)

def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    record_exception: bool = True,
    **kwargs
):
    """Decorator for adding tracing to functions."""
    def decorator(func):
        async def async_wrapper(*args, **inner_kwargs):
            tracer = get_tracer(func.__module__)
            with tracer.start_as_current_span(
                name,
                kind=kind,
                attributes=attributes,
                **kwargs
            ) as span:
                try:
                    return await func(*args, **inner_kwargs)
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        def sync_wrapper(*args, **inner_kwargs):
            tracer = get_tracer(func.__module__)
            with tracer.start_as_current_span(
                name,
                kind=kind,
                attributes=attributes,
                **kwargs
            ) as span:
                try:
                    return func(*args, **inner_kwargs)
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

# Add this to ensure the decorator works with both sync and async functions
import asyncio

__all__ = [
    'setup_tracing',
    'get_tracer',
    'trace_span',
    'instrument_fastapi',
]
