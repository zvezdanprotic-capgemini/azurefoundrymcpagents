"""
Utility functions for error handling and tracing integration.
"""
import uuid
import logging
import inspect
from typing import Optional, Dict, Any, Type, TypeVar, Callable, Awaitable, Union
from functools import wraps
from fastapi import Request, Depends
from starlette.types import ASGIApp
from opentelemetry import trace

T = TypeVar('T')

class ErrorHandlingConfig:
    """Configuration for error handling and tracing."""
    
    def __init__(
        self,
        service_name: str = "kyc-orchestrator",
        environment: str = "development",
        otlp_endpoint: Optional[str] = None,
        enable_tracing: bool = True,
        enable_error_handling: bool = True,
        log_level: str = "INFO"
    ):
        self.service_name = service_name
        self.environment = environment
        self.otlp_endpoint = otlp_endpoint
        self.enable_tracing = enable_tracing
        self.enable_error_handling = enable_error_handling
        self.log_level = log_level

def setup_app(
    app: ASGIApp,
    config: Optional[ErrorHandlingConfig] = None
) -> ASGIApp:
    """
    Set up error handling and tracing for a FastAPI application.
    
    Args:
        app: The FastAPI application
        config: Configuration for error handling and tracing
        
    Returns:
        The configured FastAPI application
    """
    config = config or ErrorHandlingConfig()
    
    # Configure logging
    logging.basicConfig(level=config.log_level)
    logger = logging.getLogger(config.service_name)
    logger.setLevel(config.log_level)
    
    # Import here to avoid circular dependency
    from .tracing import setup_tracing
    from .middleware import setup_error_handling
    
    # Set up tracing if enabled
    if config.enable_tracing:
        setup_tracing(
            service_name=config.service_name,
            environment=config.environment,
            otlp_endpoint=config.otlp_endpoint
        )
    
    # Set up error handling middleware if enabled
    if config.enable_error_handling:
        setup_error_handling(app, service_name=config.service_name)
    
    # Add request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Process the request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response
    
    return app

def handle_errors(
    error_class: Type[Exception] = Exception,
    log_level: int = logging.ERROR,
    include_request: bool = True
):
    """
    Decorator to handle errors in route handlers.
    
    Args:
        error_class: The base exception class to catch
        log_level: Log level for errors
        include_request: Whether to include request in error context
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Import here to avoid circular dependency
            from error_handling import KYCError, log_error
            
            try:
                return await func(*args, **kwargs)
            except error_class as e:
                # Re-raise KYCError as it's already properly formatted
                raise
            except Exception as e:
                # Get request from args or kwargs if needed
                request = None
                if include_request:
                    for arg in list(args) + list(kwargs.values()):
                        if isinstance(arg, Request):
                            request = arg
                            break
                
                # Log the error with context
                request_id = getattr(getattr(request, "state", None), "request_id", "")
                logger = logging.getLogger("kyc.error_handling")
                
                logger.log(
                    log_level,
                    str(e),
                    extra={"function": func.__name__, "request_id": request_id},
                    exc_info=log_level >= logging.ERROR
                )
                
                # Convert to KYCError if not already
                if not isinstance(e, KYCError):
                    e = KYCError.from_exception(e)
                
                raise e
        
        return wrapper
    return decorator

def trace_function(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
):
    """
    Decorator to trace function execution with OpenTelemetry.
    
    Args:
        name: Custom span name (defaults to function name)
        attributes: Additional attributes to add to the span
        record_exception: Whether to record exceptions in the span
    """
    # Import here at decorator definition time
    from .tracing import get_tracer
    from opentelemetry.trace import Status, StatusCode
    
    def decorator(func):
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer(func.__module__)
            with tracer.start_as_current_span(
                span_name,
                attributes=attributes or {}
            ) as span:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer(func.__module__)
            with tracer.start_as_current_span(
                span_name,
                attributes=attributes or {}
            ) as span:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

def get_request_id() -> str:
    """Dependency to get the current request ID."""
    async def _get_request_id(request: Request) -> str:
        return getattr(request.state, "request_id", "")
    return Depends(_get_request_id)
