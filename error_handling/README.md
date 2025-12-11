# Error Handling Module

A comprehensive error handling and tracing solution for the KYC Orchestrator application, built on top of FastAPI and OpenTelemetry.

## Features

- **Structured Error Handling**: Consistent error responses with proper HTTP status codes
- **Distributed Tracing**: Built-in OpenTelemetry integration for request tracing
- **Request Correlation**: Automatic request ID generation and propagation
- **Logging Integration**: Structured logging with context
- **Easy Integration**: Simple decorators for error handling and tracing

## Installation

```bash
# Add to requirements.txt
opentelemetry-api>=1.22.0
opentelemetry-sdk>=1.22.0
opentelemetry-instrumentation-fastapi>=0.43b0
opentelemetry-exporter-otlp>=1.22.0
opentelemetry-instrumentation-httpx>=0.43b0
fastapi-utils>=0.2.1
python-json-logger>=2.0.7
```

## Quick Start

### Basic Setup

```python
from fastapi import FastAPI
from error_handling import setup_app, ErrorHandlingConfig

app = FastAPI()

# Configure error handling and tracing
config = ErrorHandlingConfig(
    service_name="kyc-service",
    environment="development",
    otlp_endpoint="http://localhost:4317",  # Optional
    log_level="INFO"
)

setup_app(app, config)

# Your routes here
@app.get("/example")
async def example():
    return {"message": "Hello, World!"}
```

### Using Error Handling

```python
from fastapi import APIRouter, HTTPException
from error_handling import handle_errors, NotFoundError, ValidationError

router = APIRouter()

@router.get("/items/{item_id}")
@handle_errors()
async def get_item(item_id: str):
    if item_id == "42":
        raise NotFoundError(resource="Item", id=item_id)
    
    if not item_id.isalnum():
        raise ValidationError(
            "Item ID must be alphanumeric",
            details={"item_id": item_id}
        )
    
    return {"item_id": item_id}
```

### Using Tracing

```python
from error_handling import trace_function
import time

@trace_function()
async def process_data(data: dict):
    # This function will be automatically traced
    time.sleep(0.1)
    return {"status": "processed", **data}
```

## Error Response Format

All errors follow a consistent JSON format:

```json
{
  "error": {
    "code": "not_found",
    "message": "Item with id '42' not found",
    "details": {
      "resource": "Item",
      "id": "42"
    },
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "retryable": false
  }
}
```

## Available Error Types

- `KYCError`: Base exception class for all custom errors
- `ValidationError`: For input validation failures (HTTP 422)
- `NotFoundError`: For resources that don't exist (HTTP 404)
- `UnauthorizedError`: For authentication failures (HTTP 401)
- `ForbiddenError`: For authorization failures (HTTP 403)
- `ServiceUnavailableError`: For temporary service outages (HTTP 503)

## Configuration

The `ErrorHandlingConfig` class supports the following options:

- `service_name`: Name of your service (used in logs and traces)
- `environment`: Deployment environment (e.g., "development", "production")
- `otlp_endpoint`: OTLP endpoint for trace exporting (optional)
- `enable_tracing`: Whether to enable OpenTelemetry tracing (default: True)
- `enable_error_handling`: Whether to enable error handling middleware (default: True)
- `log_level`: Logging level (default: "INFO")

## Request Tracing

All requests automatically get:

- A unique `X-Request-ID` header
- Distributed tracing via OpenTelemetry
- Correlation between logs and traces

## Logging

Logs are structured as JSON and include:

- Timestamp
- Log level
- Request ID
- Error details (when applicable)
- Stack traces for errors

## Example Log Entry

```json
{
  "asctime": "2025-12-11 12:00:00,000",
  "levelname": "ERROR",
  "name": "kyc.error_handling",
  "message": "Item with id '42' not found",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "error_code": "not_found",
  "status_code": 404,
  "resource": "Item",
  "id": "42"
}
```

## Testing

To test error handling in your endpoints:

```python
from fastapi.testclient import TestClient
from error_handling import NotFoundError

def test_get_item_not_found():
    with pytest.raises(NotFoundError):
        response = client.get("/items/999")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
```

## Monitoring

For production monitoring, configure an OpenTelemetry collector to export traces to your preferred backend (e.g., Jaeger, Zipkin, or a commercial APM).
