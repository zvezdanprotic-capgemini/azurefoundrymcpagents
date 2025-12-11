"""
Error handling middleware for FastAPI applications.

This module provides middleware to catch and process exceptions in a consistent way.
"""
import logging
import uuid
from typing import Callable, Awaitable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

logger = logging.getLogger("kyc.error_handling")

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for handling exceptions and formatting error responses."""
    
    def __init__(self, app, service_name: str = "kyc-orchestrator"):
        super().__init__(app)
        self.service_name = service_name
    
    async def dispatch(self, request: StarletteRequest, call_next: Callable):
        """Process the request and handle any exceptions."""
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Get trace ID
        span = trace.get_current_span()
        trace_id = format(span.get_span_context().trace_id, "032x") if span and span.get_span_context().is_valid else ""
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Add request ID and trace ID to response headers
            response.headers["X-Request-ID"] = request_id
            if trace_id:
                response.headers["X-Trace-ID"] = trace_id
            
            return response
            
        except Exception as exc:
            return await self._handle_exception(exc, request_id, trace_id, request)
    
    async def _handle_exception(
        self,
        exc: Exception,
        request_id: str,
        trace_id: str,
        request: StarletteRequest
    ) -> JSONResponse:
        """Handle an exception and return an appropriate response."""
        # Import here to avoid circular dependency
        from error_handling import KYCError, ErrorResponse, log_error
        
        # Convert to KYCError if not already
        if not isinstance(exc, KYCError):
            exc = KYCError.from_exception(exc)
        
        # Log the error
        log_error(
            exc,
            logger,
            request_id=request_id,
            level=logging.ERROR if exc.status_code >= 500 else logging.WARNING,
            extra={
                "path": request.url.path,
                "method": request.method,
                "trace_id": trace_id,
            }
        )
        
        # Create error response
        error_response = ErrorResponse(
            error=exc.to_dict(request_id=request_id, trace_id=trace_id)
        )
        
        # Return JSON response
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=exc.status_code,
            headers={
                "X-Request-ID": request_id,
                "X-Trace-ID": trace_id,
                "Cache-Control": "no-store"
            }
        )

def setup_error_handling(app, service_name: str = "kyc-orchestrator") -> None:
    """Set up error handling middleware for a FastAPI application."""
    from error_handling import KYCError, ErrorResponse, log_error
    
    app.add_middleware(ErrorHandlingMiddleware, service_name=service_name)
    
    @app.exception_handler(KYCError)
    async def kyc_error_handler(request: Request, exc: KYCError) -> JSONResponse:
        """Handle KYCError exceptions."""
        request_id = request.headers.get("x-request-id", "")
        span = trace.get_current_span()
        trace_id = format(span.get_span_context().trace_id, "032x") if span else ""
        
        log_error(
            exc,
            logger,
            request_id=request_id,
            level=logging.WARNING if exc.status_code < 500 else logging.ERROR,
            extra={
                "path": request.url.path,
                "method": request.method,
                "trace_id": trace_id,
            }
        )
        
        # Special-case 404 to match FastAPI "detail" format expected by tests
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.message},
                headers={
                    "X-Request-ID": request_id,
                    "X-Trace-ID": trace_id,
                    "Cache-Control": "no-store"
                }
            )
        else:
            return JSONResponse(
                status_code=exc.status_code,
                content=ErrorResponse(
                    error=exc.to_dict(request_id=request_id, trace_id=trace_id)
                ).model_dump(),
                headers={
                    "X-Request-ID": request_id,
                    "X-Trace-ID": trace_id,
                    "Cache-Control": "no-store"
                }
            )
    
    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        from . import KYCError, ErrorCode
        
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        span = trace.get_current_span()
        trace_id = format(span.get_span_context().trace_id, "032x") if span else ""
        
        # Log the full exception
        logger.error(
            f"Unhandled exception: {str(exc)}",
            exc_info=exc,
            extra={
                "request_id": request_id,
                "trace_id": trace_id,
                "path": request.url.path,
                "method": request.method,
            }
        )
        
        # Create a generic error response
        error = KYCError(
            code=ErrorCode.UNKNOWN_ERROR,
            message="An unexpected error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc)
            }
        )
        
        return JSONResponse(
            status_code=error.status_code,
            content=ErrorResponse(
                error=error.to_dict(request_id=request_id, trace_id=trace_id)
            ).model_dump(),
            headers={
                "X-Request-ID": request_id,
                "X-Trace-ID": trace_id,
                "Cache-Control": "no-store"
            }
        )
