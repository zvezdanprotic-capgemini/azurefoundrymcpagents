"""Tests for MCP server health monitoring."""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
import httpx
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
async def test_get_server_health_all_healthy(mcp_client):
    """Test health check when all servers are healthy."""
    # Mock successful health checks for all servers
    mock_response = Mock()
    mock_response.status_code = 200
    mcp_client._http_client.get = AsyncMock(return_value=mock_response)
    
    health_status = await mcp_client.get_server_health()
    
    # All servers should be healthy
    assert health_status["postgres"] is True
    assert health_status["blob"] is True
    assert health_status["email"] is True
    assert health_status["rag"] is True
    
    # Should have called health endpoint for each server
    assert mcp_client._http_client.get.call_count == 4


@pytest.mark.asyncio
async def test_get_server_health_partial_failure(mcp_client):
    """Test health check when some servers are down."""
    # Mock mixed health check results
    call_count = 0
    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_response = Mock()
        # postgres and blob healthy (8001, 8002), email and rag down (8003, 8004)
        if ":8001" in url or ":8002" in url:
            mock_response.status_code = 200
        else:
            mock_response.status_code = 503
        return mock_response
    
    mcp_client._http_client.get = AsyncMock(side_effect=mock_get)
    
    health_status = await mcp_client.get_server_health()
    
    # Check health status
    assert health_status["postgres"] is True
    assert health_status["blob"] is True
    assert health_status["email"] is False
    assert health_status["rag"] is False
    
    # Should have checked all servers
    assert call_count == 4


@pytest.mark.asyncio
async def test_get_server_health_network_error(mcp_client):
    """Test health check when network errors occur."""
    # Mock network errors
    async def mock_get_with_error(url, **kwargs):
        if ":8001" in url:  # postgres
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response
        else:
            raise httpx.ConnectError("Connection refused")
    
    mcp_client._http_client.get = AsyncMock(side_effect=mock_get_with_error)
    
    health_status = await mcp_client.get_server_health()
    
    # Only postgres should be healthy
    assert health_status["postgres"] is True
    assert health_status["blob"] is False
    assert health_status["email"] is False
    assert health_status["rag"] is False


@pytest.mark.asyncio
async def test_get_server_health_timeout(mcp_client):
    """Test health check with timeout errors."""
    # Mock timeout for some servers
    call_count = 0
    async def mock_get_with_timeout(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if ":8001" in url or ":8002" in url:  # postgres and blob
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response
        else:
            raise httpx.TimeoutException("Timeout")
    
    mcp_client._http_client.get = AsyncMock(side_effect=mock_get_with_timeout)
    
    health_status = await mcp_client.get_server_health()
    
    # Servers that timed out should be marked unhealthy
    assert health_status["postgres"] is True
    assert health_status["blob"] is True
    assert health_status["email"] is False
    assert health_status["rag"] is False
    assert call_count == 4


@pytest.mark.asyncio
async def test_get_server_health_respects_timeout(mcp_client):
    """Test that health checks include timeout parameter."""
    mock_response = Mock()
    mock_response.status_code = 200
    mcp_client._http_client.get = AsyncMock(return_value=mock_response)
    
    await mcp_client.get_server_health()
    
    # Check that timeout was passed to all requests
    for call in mcp_client._http_client.get.call_args_list:
        assert call[1].get("timeout") == 5.0


@pytest.mark.asyncio
async def test_health_check_returns_dict(mcp_client):
    """Test that health check returns proper dict structure."""
    mock_response = Mock()
    mock_response.status_code = 200
    mcp_client._http_client.get = AsyncMock(return_value=mock_response)
    
    health_status = await mcp_client.get_server_health()
    
    # Should be a dictionary
    assert isinstance(health_status, dict)
    
    # Should have all expected server names as keys
    assert set(health_status.keys()) == {"postgres", "blob", "email", "rag"}
    
    # All values should be boolean
    for value in health_status.values():
        assert isinstance(value, bool)
