"""
HTTP MCP Server Health Endpoint Tests

Tests the /health endpoint of each MCP server to ensure servers are running.
MCP protocol functionality (tool listing, tool calling) is tested via the MCP client
in test_main_http.py, test_integration_http.py, and test_agents_http.py.

Rationale for not testing /mcp endpoint directly:
- FastMCP uses Streamable HTTP protocol (SSE-based) requiring session establishment
- Direct JSON-RPC POSTs are not supported by the Streamable HTTP transport
- Proper MCP client handles this protocol automatically and is tested extensively
- Testing raw protocol would duplicate client tests without adding value
- These tests verify servers are running; functional tests use proper MCP client
"""
import pytest
import httpx


MCP_SERVERS = {
    "postgres": "http://127.0.0.1:8001",
    "blob": "http://127.0.0.1:8002",
    "email": "http://127.0.0.1:8003",
    "rag": "http://127.0.0.1:8004",
}


@pytest.mark.usefixtures("mcp_server_processes")
class TestPostgresHTTPServer:
    """Test PostgreSQL HTTP MCP Server."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test Postgres server health endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MCP_SERVERS['postgres']}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "service" in data


@pytest.mark.usefixtures("mcp_server_processes")
class TestBlobHTTPServer:
    """Test Blob Storage HTTP MCP Server."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test Blob server health endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MCP_SERVERS['blob']}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "service" in data


@pytest.mark.usefixtures("mcp_server_processes")
class TestEmailHTTPServer:
    """Test Email HTTP MCP Server."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test Email server health endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MCP_SERVERS['email']}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "service" in data


@pytest.mark.usefixtures("mcp_server_processes")
class TestRAGHTTPServer:
    """Test RAG HTTP MCP Server."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test RAG server health endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MCP_SERVERS['rag']}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "service" in data


@pytest.mark.usefixtures("mcp_server_processes")
class TestAllServersHealth:
    """Test all servers are healthy."""
    
    @pytest.mark.asyncio
    async def test_all_servers_responding(self):
        """Test all 4 HTTP MCP servers are responding to health checks."""
        async with httpx.AsyncClient() as client:
            for name, url in MCP_SERVERS.items():
                response = await client.get(f"{url}/health", timeout=5.0)
                assert response.status_code == 200, f"{name} server not responding"
                data = response.json()
                assert data["status"] == "ok", f"{name} server not healthy"
                print(f"✓ {name} server healthy")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
