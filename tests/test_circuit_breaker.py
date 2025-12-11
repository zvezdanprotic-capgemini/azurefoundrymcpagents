"""
Tests for Circuit Breaker functionality in MCP Client
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from mcp_client import KYCMCPClient
from aiobreaker import CircuitBreaker, CircuitBreakerState


@pytest_asyncio.fixture
async def mcp_client():
    """Create MCP client for testing."""
    client = KYCMCPClient(
        postgres_url="http://127.0.0.1:8001/mcp",
        blob_url="http://127.0.0.1:8002/mcp",
        email_url="http://127.0.0.1:8003/mcp",
        rag_url="http://127.0.0.1:8004/mcp"
    )
    
    # Mock the HTTP client
    client._http_client = AsyncMock()
    
    # Mock MultiServerMCPClient
    mock_instance = AsyncMock()
    
    # Mock tool
    mock_tool = Mock()
    mock_tool.name = "postgres__test_tool"
    mock_tool.ainvoke = AsyncMock(return_value={"result": "success"})
    
    mock_instance.get_tools = AsyncMock(return_value=[mock_tool])
    
    client._client = mock_instance
    client._tools = [mock_tool]
    client._connected = True
    
    yield client
    
    await client.close()


@pytest.mark.asyncio
async def test_circuit_breaker_normal_operation(mcp_client):
    """Test that circuit breaker allows normal operations."""
    # Get the tool
    tool = mcp_client._tools[0]
    
    # Should succeed normally
    result = await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})
    
    assert result == {"result": "success"}
    assert tool.ainvoke.called
    assert mcp_client._circuit_breaker.current_state == CircuitBreakerState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures(mcp_client):
    """Test that circuit breaker opens after failure threshold."""
    # Get the tool and make it fail
    tool = mcp_client._tools[0]
    tool.ainvoke = AsyncMock(side_effect=Exception("Service error"))
    
    # Trigger failures (fail_max=5)
    for i in range(5):
        with pytest.raises(Exception):
            await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})
    
    # Circuit should now be open
    assert mcp_client._circuit_breaker.current_state == CircuitBreakerState.OPEN
    
    # Next call should fail immediately with CircuitBreakerError
    with pytest.raises(RuntimeError, match="Service temporarily unavailable"):
        await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery(mcp_client):
    """Test circuit breaker recovery after timeout."""
    # Get the tool
    tool = mcp_client._tools[0]
    
    # Force circuit breaker to open with shorter timeout
    import asyncio
    from datetime import timedelta
    
    # Create a new circuit breaker with 1 second timeout for testing
    mcp_client._circuit_breaker = CircuitBreaker(
        fail_max=2,
        timeout_duration=timedelta(seconds=1),
        name="test_recovery"
    )
    
    # Force circuit breaker to open
    tool.ainvoke = AsyncMock(side_effect=Exception("Service error"))
    for i in range(2):
        with pytest.raises(Exception):
            await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})
    
    assert mcp_client._circuit_breaker.current_state == CircuitBreakerState.OPEN
    
    # Circuit should reject immediately when open
    with pytest.raises(RuntimeError, match="Service temporarily unavailable"):
        await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})
    
    # Wait for timeout to transition to half-open
    await asyncio.sleep(1.1)
    
    # Fix the tool
    tool.ainvoke = AsyncMock(return_value={"result": "recovered"})
    
    # Should succeed and close circuit
    result = await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})
    assert result == {"result": "recovered"}
    assert mcp_client._circuit_breaker.current_state == CircuitBreakerState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_per_client_instance(mcp_client):
    """Test that circuit breaker state is per client instance."""
    # Create another client
    client2 = KYCMCPClient()
    client2._http_client = AsyncMock()
    
    mock_tool2 = Mock()
    mock_tool2.name = "test_tool"
    mock_tool2.ainvoke = AsyncMock(return_value={"result": "success"})
    client2._tools = [mock_tool2]
    client2._client = AsyncMock()
    client2._connected = True
    
    # Open circuit on first client
    tool = mcp_client._tools[0]
    tool.ainvoke = AsyncMock(side_effect=Exception("Service error"))
    for i in range(5):
        with pytest.raises(Exception):
            await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})
    
    assert mcp_client._circuit_breaker.current_state == CircuitBreakerState.OPEN
    
    # Second client should have independent circuit breaker (closed)
    assert client2._circuit_breaker.current_state == CircuitBreakerState.CLOSED
    
    await client2.close()


@pytest.mark.asyncio
async def test_circuit_breaker_with_tracing(mcp_client):
    """Test that circuit breaker works with tracing enabled."""
    from error_handling import get_tracer
    
    tracer = get_tracer()
    
    # Normal operation should set success status
    result = await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})
    assert result == {"result": "success"}
    
    # Make tool fail and trigger circuit breaker
    tool = mcp_client._tools[0]
    tool.ainvoke = AsyncMock(side_effect=Exception("Service error"))
    
    for i in range(5):
        with pytest.raises(Exception):
            await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})
    
    # Circuit open - should raise RuntimeError
    with pytest.raises(RuntimeError, match="Service temporarily unavailable"):
        await mcp_client.call_tool("postgres__test_tool", {"arg": "value"})
