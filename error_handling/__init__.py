"""
Error handling module for the KYC Orchestrator.

This module provides a structured way to handle and report errors across the application.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Type, Union, List
import logging
from fastapi import status
from pydantic import BaseModel

# Import all from submodules to make them available at the package level
from .tracing import *
from .middleware import *
from .utils import *

# Re-export all error-related classes and functions
__all__ = [
    # Error codes and base classes
    'ErrorCode',
    'ErrorDetails',
    'ErrorResponse',
    'KYCError',
    
    # Common error types
    'ValidationError',
    'NotFoundError',
    'UnauthorizedError',
    'ForbiddenError',
    'ServiceUnavailableError',
    
    # Utility functions
    'log_error',
    'setup_error_handling',
    'ErrorHandlingMiddleware',
    
    # Tracing
    'setup_tracing',
    'get_tracer',
    'trace_span',
    'instrument_fastapi',
    
    # Utils
    'ErrorHandlingConfig',
    'setup_app',
    'handle_errors',
    'trace_function',
    'get_request_id',
]

class ErrorCode(str, Enum):
    """Standard error codes for the application."""
    # Infrastructure Errors (1xx)
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT_ERROR = "timeout_error"
    NETWORK_ERROR = "network_error"
    DATABASE_ERROR = "database_error"
    
    # Business Logic Errors (2xx)
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    INVALID_STATE = "invalid_state"
    
    # Integration Errors (3xx)
    INTEGRATION_ERROR = "integration_error"
    INVALID_RESPONSE = "invalid_response"
    RATE_LIMITED = "rate_limited"
    
    # Security Errors (4xx)
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    INVALID_TOKEN = "invalid_token"
    
    # Unknown Error (999)
    UNKNOWN_ERROR = "unknown_error"

@dataclass
class ErrorDetails:
    """Structured error details for consistent error reporting."""
    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    retryable: bool = False

class ErrorResponse(BaseModel):
    """Standard error response format for API responses."""
    error: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "validation_error",
                    "message": "Invalid input data",
                    "details": {"field": "email", "error": "Invalid email format"},
                    "request_id": "req_12345",
                    "trace_id": "trace_12345"
                }
            }
        }

class KYCError(Exception):
    """Base exception class for all KYC application errors."""
    
    def __init__(
        self,
        code: Union[ErrorCode, str],
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        retryable: bool = False
    ):
        self.code = ErrorCode(code) if isinstance(code, str) else code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.cause = cause
        self.retryable = retryable
        super().__init__(message)
    
    def to_dict(self, request_id: str = "", trace_id: str = "") -> Dict[str, Any]:
        """Convert the error to a dictionary for JSON serialization."""
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "request_id": request_id,
            "trace_id": trace_id,
            "retryable": self.retryable
        }
    
    @classmethod
    def from_exception(cls, exc: Exception) -> 'KYCError':
        """Create a KYCError from a generic exception."""
        if isinstance(exc, KYCError):
            return exc
        return cls(
            code=ErrorCode.UNKNOWN_ERROR,
            message=str(exc) or "An unknown error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"exception_type": exc.__class__.__name__},
            cause=exc
        )

# Common error types for easy reuse
class ValidationError(KYCError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )

class NotFoundError(KYCError):
    def __init__(self, resource: str, id: str, message: Optional[str] = None):
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=message or f"{resource} with id '{id}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "id": id}
        )

class UnauthorizedError(KYCError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )

class ForbiddenError(KYCError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )

class ServiceUnavailableError(KYCError):
    def __init__(self, service: str, cause: Optional[Exception] = None):
        super().__init__(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message=f"{service} service is currently unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"service": service},
            cause=cause,
            retryable=True
        )

def log_error(
    error: Exception,
    logger: logging.Logger,
    request_id: str = "",
    level: int = logging.ERROR,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Helper function to log errors with structured context.
    
    Args:
        error: The exception to log
        logger: Logger instance to use
        request_id: Optional request ID for correlation
        level: Log level (default: ERROR)
        extra: Additional context to include in the log
    """
    extra = extra or {}
    if request_id:
        extra["request_id"] = request_id
    
    if isinstance(error, KYCError):
        extra.update({
            "error_code": error.code.value,
            "status_code": error.status_code,
            "retryable": error.retryable,
            **error.details
        })
        if error.cause:
            extra["cause"] = str(error.cause)
    else:
        extra.update({
            "error_type": error.__class__.__name__,
            "error_message": str(error)
        })
    
    logger.log(level, str(error), extra=extra, exc_info=level >= logging.ERROR)
