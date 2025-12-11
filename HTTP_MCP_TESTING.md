# HTTP MCP Testing Guide

This guide explains how to test the HTTP MCP architecture where MCP servers run as independent processes.

## Overview

The HTTP MCP test suite validates:
- ✅ Individual HTTP MCP servers (Postgres, Blob, Email, RAG)
- ✅ HTTP MCP client integration with langchain-mcp-adapters
- ✅ FastAPI application using HTTP MCP (main_http.py)
- ✅ Agents working with HTTP MCP tools
- ✅ End-to-end KYC workflow with decoupled services

## Test Files

### New HTTP MCP Tests

| File | Purpose | Requires Servers |
|------|---------|------------------|
| `tests/conftest.py` | Pytest fixtures for HTTP MCP (auto-starts servers) | ✓ |
| `tests/test_main_http.py` | FastAPI app with HTTP MCP client | ✓ |
| `tests/test_agents_http.py` | Agents using HTTP MCP tools | ✓ |
| `tests/test_integration_http.py` | End-to-end workflow tests | ✓ |
| `tests/test_mcp_servers_http.py` | Individual server HTTP tests | ✓ |

### Legacy Tests (Embedded MCP)

These tests are for the old embedded MCP architecture (main.py):
- `test_main.py` - Original FastAPI tests
- `test_local_agents.py` - Original agent tests
- `test_graph_flow.py` - Graph orchestration
- `test_mcp_postgres_integration.py` - Direct MCP server calls
- `test_mcp_blob_integration.py` - Direct MCP server calls
- `test_mcp_email_integration.py` - Direct MCP server calls
- `test_mcp_rag_integration.py` - Direct MCP server calls

## Quick Start

### 1. Install Test Dependencies

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx
```

### 2. Start HTTP MCP Servers

The test suite can auto-start servers, or you can start them manually:

```bash
# Option A: Manual start (recommended)
./start_all_mcp_servers.sh

# Option B: Let test runner start them
# (will prompt you)
```

### 3. Run All HTTP MCP Tests

```bash
# Run all HTTP MCP tests
python run_http_mcp_tests.py

# Or use pytest directly
pytest tests/test_*_http.py -v
```

## Test Runner Options

The `run_http_mcp_tests.py` script provides several options:

```bash
# Run all HTTP MCP tests (default)
python run_http_mcp_tests.py

# Run specific test file
python run_http_mcp_tests.py tests/test_main_http.py

# Run with verbose output
python run_http_mcp_tests.py -v

# Run only fast unit tests (skip integration)
python run_http_mcp_tests.py --quick

# Run only integration tests
python run_http_mcp_tests.py --integration

# Run tests with specific markers
python run_http_mcp_tests.py -m "not slow"
```

## Using Pytest Directly

```bash
# Run all HTTP MCP tests
pytest tests/test_*_http.py -v

# Run specific test class
pytest tests/test_main_http.py::TestMainHTTPApplication -v

# Run specific test
pytest tests/test_main_http.py::TestMainHTTPApplication::test_health_endpoint -v

# Run with coverage
pytest tests/test_*_http.py --cov=. --cov-report=html

# Run integration tests only
pytest -m integration -v

# Run excluding integration tests
pytest -m "not integration" -v
```

## Test Architecture

### Pytest Fixtures (conftest.py)

The `conftest.py` file provides fixtures that:

1. **mcp_server_processes** (session scope)
   - Starts all 4 HTTP MCP servers before tests
   - Waits for servers to be ready
   - Stops servers after all tests complete
   - Reuses already-running servers if available

2. **mcp_client** (session scope)
   - Initializes HTTP MCP client
   - Connects to all 4 servers
   - Provides client instance to tests

3. **test_session_data** (function scope)
   - Provides mock session data for tests

4. **mock_customer_input** (function scope)
   - Provides mock customer input for tests

### Test Organization

```
tests/
├── conftest.py                    # Pytest fixtures (server startup)
├── test_main_http.py              # FastAPI app tests
│   ├── TestMainHTTPApplication    # Basic endpoints
│   ├── TestChatEndpoint           # Chat functionality
│   └── TestDocumentEndpoints      # Document operations
├── test_agents_http.py            # Agent tests
│   ├── TestBaseAgentHTTP          # Base agent functionality
│   ├── TestHTTPMCPIntegration     # Tool loading
│   ├── TestAgentInvocation        # Agent invocation
│   └── TestMCPClientTools         # Client tool calls
├── test_integration_http.py       # End-to-end tests
│   └── Various integration tests
└── test_mcp_servers_http.py       # Individual server tests
    ├── TestPostgresHTTPServer
    ├── TestBlobHTTPServer
    ├── TestEmailHTTPServer
    └── TestRAGHTTPServer
```

## Test Markers

Tests use pytest markers for categorization:

```python
@pytest.mark.integration      # Integration test (slower)
@pytest.mark.asyncio          # Async test
@pytest.mark.usefixtures("mcp_server_processes")  # Requires servers
```

Run specific markers:
```bash
pytest -m integration      # Only integration tests
pytest -m "not integration"  # Exclude integration tests
```

## Manual Server Testing

### Test Individual Servers

```bash
# Test Postgres server
curl http://127.0.0.1:8001/health

# Test Blob server
curl http://127.0.0.1:8002/health

# Test Email server
curl http://127.0.0.1:8003/health

# Test RAG server
curl http://127.0.0.1:8004/health
```

### Test MCP Protocol

```bash
# List tools from Postgres server
curl -X POST http://127.0.0.1:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'

# Call a tool
curl -X POST http://127.0.0.1:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_customer_by_email",
      "arguments": {"email": "test@example.com"}
    }
  }'
```

## Troubleshooting

### Servers Not Starting

```bash
# Check if ports are in use
lsof -i :8001
lsof -i :8002
lsof -i :8003
lsof -i :8004

# Kill processes on ports
kill -9 $(lsof -ti:8001)
kill -9 $(lsof -ti:8002)
kill -9 $(lsof -ti:8003)
kill -9 $(lsof -ti:8004)

# Start servers manually
./start_all_mcp_servers.sh
```

### Tests Failing

```bash
# Verify servers are running
python test_mcp_servers.py

# Check server logs
# (servers log to stdout/stderr when started)

# Run single test with verbose output
pytest tests/test_main_http.py::TestMainHTTPApplication::test_health_endpoint -vv
```

### Environment Issues

```bash
# Ensure .env file is configured
cp .env.example .env
# Edit .env with your Azure credentials

# Verify Python environment
source venv/bin/activate
pip install -r requirements.txt

# Check MCP dependencies
pip list | grep mcp
# Should show:
#   mcp>=1.0.0
#   langchain-mcp-adapters>=0.1.0
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: HTTP MCP Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx
      
      - name: Start HTTP MCP servers
        run: ./start_all_mcp_servers.sh
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/kyc
      
      - name: Run HTTP MCP tests
        run: python run_http_mcp_tests.py
```

## Performance Testing

### Load Testing HTTP MCP Servers

```bash
# Install locust
pip install locust

# Create locustfile.py (example)
# Then run:
locust -f locustfile.py --host=http://127.0.0.1:8001
```

### Benchmark Tests

```bash
# Run tests with timing
pytest tests/test_*_http.py --durations=10

# Profile tests
pytest tests/test_*_http.py --profile
```

## Coverage Reports

```bash
# Generate coverage report
pytest tests/test_*_http.py --cov=. --cov-report=html

# Open coverage report
open htmlcov/index.html

# Text coverage report
pytest tests/test_*_http.py --cov=. --cov-report=term-missing
```

## Best Practices

### 1. Use Fixtures
```python
@pytest.mark.usefixtures("mcp_server_processes")
class TestMyFeature:
    """Tests requiring HTTP MCP servers."""
    pass
```

### 2. Async Tests
```python
@pytest.mark.asyncio
async def test_async_operation(mcp_client):
    result = await mcp_client.call_tool("tool_name", {})
    assert result is not None
```

### 3. Test Isolation
```python
def setup_method(self):
    """Clear state before each test."""
    sessions.clear()
```

### 4. Meaningful Assertions
```python
# Bad
assert response.status_code == 200

# Good
assert response.status_code == 200, f"Server returned {response.text}"
assert "session_id" in data, "Response missing session_id field"
```

## Next Steps

1. **Run the tests**: `python run_http_mcp_tests.py`
2. **Check coverage**: `pytest --cov=. --cov-report=html`
3. **Add new tests**: Follow the patterns in existing test files
4. **CI/CD**: Integrate tests into your CI/CD pipeline

## Support

- Check logs in terminal where servers are running
- Review `HTTP_MCP_SETUP.md` for architecture details
- See `HTTP_MCP_README.md` for quick reference
- Examine `conftest.py` for fixture details
