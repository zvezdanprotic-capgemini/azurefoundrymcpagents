"""Tests for OpenTelemetry tracing in MCP client."""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from mcp_client import KYCMCPClient


@pytest_asyncio.fixture
async def mcp_client():
    """Create a KYCMCPClient for testing."""
    client = KYCMCPClient()
    
    # Mock the client and tools
    client._client = AsyncMock()
    client._connected = True
    client._http_client = AsyncMock()
    
    mock_tool = Mock()
    mock_tool.name = "test_tool"
    mock_tool.ainvoke = AsyncMock(return_value={"result": "success"})
    client._tools = [mock_tool]
    
    yield client
    
    # Cleanup
    if client._http_client:
        await client._http_client.aclose()


@pytest.mark.asyncio
async def test_call_tool_creates_span(mcp_client):
    """Test that call_tool creates an OpenTelemetry span."""
    from error_handling import get_tracer
    
    # Mock the tracer
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
    
    with patch("mcp_client.get_tracer", return_value=mock_tracer):
        result = await mcp_client.call_tool("test_tool", {"arg": "value"})
    
    # Verify span was created with correct name
    mock_tracer.start_as_current_span.assert_called_once_with("mcp.tool.test_tool")
    
    # Verify result
    assert result == {"result": "success"}


@pytest.mark.asyncio
async def test_call_tool_sets_span_attributes(mcp_client):
    """Test that call_tool sets correct span attributes."""
    from error_handling import get_tracer
    
    # Mock the tracer
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
    
    with patch("mcp_client.get_tracer", return_value=mock_tracer):
        await mcp_client.call_tool("test_tool", {"key": "value", "number": 42})
    
    # Verify attributes were set
    calls = mock_span.set_attribute.call_args_list
    assert len(calls) == 3
    
    # Check attribute names
    attribute_names = [call[0][0] for call in calls]
    assert "mcp.tool.name" in attribute_names
    assert "mcp.tool.arguments" in attribute_names
    assert "mcp.tool.status" in attribute_names


@pytest.mark.asyncio
async def test_call_tool_span_status_success(mcp_client):
    """Test that span has success status for successful calls."""
    from error_handling import get_tracer
    
    # Mock the tracer
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
    
    with patch("mcp_client.get_tracer", return_value=mock_tracer):
        await mcp_client.call_tool("test_tool", {"arg": "value"})
    
    # Find the status attribute call
    status_calls = [call for call in mock_span.set_attribute.call_args_list 
                   if call[0][0] == "mcp.tool.status"]
    assert len(status_calls) == 1
    assert status_calls[0][0][1] == "success"


@pytest.mark.asyncio
async def test_call_tool_span_status_error(mcp_client):
    """Test that span has error status for failed calls."""
    from error_handling import get_tracer
    
    # Make tool fail
    tool = mcp_client._tools[0]
    tool.ainvoke = AsyncMock(side_effect=Exception("Tool error"))
    
    # Mock the tracer
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
    
    with patch("mcp_client.get_tracer", return_value=mock_tracer):
        with pytest.raises(Exception):
            await mcp_client.call_tool("test_tool", {"arg": "value"})
    
    # Find the status attribute calls
    status_calls = [call for call in mock_span.set_attribute.call_args_list 
                   if call[0][0] == "mcp.tool.status"]
    assert len(status_calls) == 1
    assert status_calls[0][0][1] == "error"
    
    # Should also have error message
    error_calls = [call for call in mock_span.set_attribute.call_args_list 
                  if call[0][0] == "mcp.tool.error"]
    assert len(error_calls) == 1
    assert "Tool error" in error_calls[0][0][1]


@pytest.mark.asyncio
async def test_get_tools_creates_span(mcp_client):
    """Test that get_tools creates an OpenTelemetry span."""
    from error_handling import get_tracer
    
    # Mock the tracer
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
    
    with patch("mcp_client.get_tracer", return_value=mock_tracer):
        tools = await mcp_client.get_tools()
    
    # Verify span was created with correct name
    mock_tracer.start_as_current_span.assert_called_once_with("mcp.get_tools")
    
    # Verify result
    assert len(tools) == 1
    assert tools[0].name == "test_tool"


@pytest.mark.asyncio
async def test_circuit_breaker_open_span_status(mcp_client):
    """Test that span has circuit_open status when circuit breaker opens."""
    from error_handling import get_tracer
    from datetime import timedelta
    from aiobreaker import CircuitBreaker
    
    # Replace circuit breaker with shorter timeout
    mcp_client._circuit_breaker = CircuitBreaker(
        fail_max=2,
        timeout_duration=timedelta(seconds=60),
        name="test"
    )
    
    # Make tool fail to open circuit
    tool = mcp_client._tools[0]
    tool.ainvoke = AsyncMock(side_effect=Exception("Service error"))
    
    # Open the circuit
    for i in range(2):
        with pytest.raises(Exception):
            await mcp_client.call_tool("test_tool", {"arg": "value"})
    
    # Mock the tracer for the next call
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)
    
    # Try to call with circuit open
    with patch("mcp_client.get_tracer", return_value=mock_tracer):
        with pytest.raises(RuntimeError, match="Service temporarily unavailable"):
            await mcp_client.call_tool("test_tool", {"arg": "value"})
    
    # Find the status attribute calls
    status_calls = [call for call in mock_span.set_attribute.call_args_list 
                   if call[0][0] == "mcp.tool.status"]
    assert len(status_calls) == 1
    assert status_calls[0][0][1] == "circuit_open"
