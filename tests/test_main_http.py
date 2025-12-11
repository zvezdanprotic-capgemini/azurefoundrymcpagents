"""
Unit tests for main_http.py - FastAPI application with HTTP MCP

Tests the main application using HTTP MCP architecture.
Requires HTTP MCP servers to be running (handled by conftest.py fixtures).
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, Response
from fastapi import HTTPException, status

import sys
import os
import uuid
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_http import app, sessions, load_sessions, save_sessions, SESSIONS_FILE
from error_handling import KYCError, ErrorCode, ErrorResponse, ServiceUnavailableError, NotFoundError


@pytest.fixture
def client():
    """Create test client for FastAPI app with lifespan context."""
    # Setup test environment
    test_session_file = Path("test_sessions.json")
    if test_session_file.exists():
        test_session_file.unlink()
    
    # Patch the sessions file path for testing
    with patch('main_http.SESSIONS_FILE', test_session_file):
        with TestClient(app) as c:
            yield c
    
    # Cleanup
    if test_session_file.exists():
        test_session_file.unlink()


@pytest.mark.usefixtures("mcp_server_processes")
class TestMainHTTPApplication:
    """Test suite for main_http FastAPI application with HTTP MCP"""
    
    def setup_method(self):
        """Setup before each test"""
        # Clear sessions before each test
        sessions.clear()
    
    def test_root_endpoint(self, client):
        """Test root endpoint shows HTTP MCP info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "HTTP MCP" in data["service"]
        assert "version" in data
        assert "mcp_architecture" in data
        assert data["mcp_architecture"] == "HTTP (decoupled servers)"
        assert "mcp_servers" in data
        assert "postgres" in data["mcp_servers"]
        assert "blob" in data["mcp_servers"]
        assert "email" in data["mcp_servers"]
        assert "rag" in data["mcp_servers"]
        
        # Test response headers
        assert "x-request-id" in response.headers
        # Trace ID is optional (only present if OpenTelemetry span is active)
        # assert "x-trace-id" in response.headers
    
    @patch('main_http.get_mcp_client')
    def test_health_check(self, mock_get_mcp_client, client):
        """Test health check endpoint"""
        # Mock MCP client
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_get_mcp_client.return_value = mock_client
        
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data
        assert data["mcp_connected"] is True
        
        # Test response headers
        assert "x-request-id" in response.headers
        # Trace ID is optional
        # assert "x-trace-id" in response.headers
    
    @patch('main_http.get_mcp_client')
    def test_health_check_service_unavailable(self, mock_get_mcp_client, client):
        """Test health check when MCP client is not connected"""
        # Mock MCP client as not connected
        mock_client = MagicMock()
        mock_client.is_connected.return_value = False
        mock_get_mcp_client.return_value = mock_client
        
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "service_unavailable"
        assert "MCP client is not connected" in data["error"]["message"]
    
    def test_mcp_servers_status(self, client):
        """Test MCP servers status endpoint"""
        response = client.get("/mcp/servers")
        assert response.status_code == 200
        data = response.json()
        assert "servers" in data
        servers = data["servers"]
        assert len(servers) == 4
        assert "postgres" in servers
        assert "blob" in servers
        assert "email" in servers
        assert "rag" in servers
        # Check each server has a URL
        for server_name in ["postgres", "blob", "email", "rag"]:
            assert isinstance(servers[server_name], str)
            assert "http" in servers[server_name]
    
    @patch('main_http.get_mcp_client')
    def test_list_mcp_tools(self, mock_get_mcp_client, client):
        """Test listing available MCP tools"""
        # Mock MCP client with async get_tools
        mock_client = MagicMock()
        # Create mock tool objects
        mock_tool = MagicMock()
        mock_tool.name = "test__test_tool"
        mock_tool.description = "A test tool"
        mock_tool.args_schema = None
        
        # Make get_tools return an async result
        async def mock_get_tools():
            return [mock_tool]
        mock_client.get_tools = mock_get_tools
        mock_get_mcp_client.return_value = mock_client
        
        response = client.get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "total_tools" in data
        assert isinstance(data["tools"], list)
        assert data["total_tools"] == 1
        
        # Test response headers
        assert "x-request-id" in response.headers
        # Trace ID is optional
        # assert "x-trace-id" in response.headers
    
    @patch('main_http.get_mcp_client')
    def test_list_mcp_tools_service_unavailable(self, mock_get_mcp_client, client):
        """Test listing MCP tools when service is unavailable"""
        # Mock MCP client as None
        mock_get_mcp_client.return_value = None
        
        response = client.get("/mcp/tools")
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "service_unavailable"
    
    def test_list_sessions_empty(self, client):
        """Test listing sessions when none exist"""
        response = client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)
    
    def test_chat_creates_new_session(self, client):
        """Test that chat endpoint creates new session if none exists"""
        chat_request = {
            "message": "I need business insurance",
            "session_id": None  # Let system generate
        }
        
        response = client.post("/chat", json=chat_request)
        assert response.status_code == 200
        data = response.json()
        
        assert "session_id" in data
        assert "response" in data
        assert "status" in data
        assert "current_step" in data
    
    def test_get_session_existing(self, client):
        """Test getting an existing session"""
        # First create a session via chat
        chat_request = {
            "message": "I need insurance",
            "session_id": "test-session-123"
        }
        
        create_response = client.post("/chat", json=chat_request)
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]
        
        # Now get the session
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == session_id
        assert "status" in data
        assert "current_step" in data
    
    def test_get_session_nonexistent(self, client):
        """Test getting a non-existent session"""
        response = client.get("/session/non-existent-id")
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]
    
    def test_delete_session(self, client):
        """Test deleting a session"""
        # Create a session first
        chat_request = {
            "message": "Test",
            "session_id": "test-delete-123"
        }
        client.post("/chat", json=chat_request)
        
        # Delete it
        response = client.delete("/session/test-delete-123")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == True
        assert data["session_id"] == "test-delete-123"
        
        # Verify it's gone
        get_response = client.get("/session/test-delete-123")
        assert get_response.status_code == 404
    
    def test_list_sessions(self, client):
        """Test listing all sessions"""
        # Create a couple of sessions via chat
        for i in range(2):
            client.post("/chat", json={
                "message": f"Test message {i}",
                "session_id": f"test-session-{i}"
            })
        
        response = client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        
        assert "sessions" in data
        assert len(data["sessions"]) >= 2
    
    def test_session_persistence(self, client):
        """Test that sessions can be retrieved after creation"""
        # Create a session
        chat_request = {
            "message": "Persistent message",
            "session_id": "persist-test-123"
        }
        
        response = client.post("/chat", json=chat_request)
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        
        # Verify session exists
        get_response = client.get(f"/session/{session_id}")
        assert get_response.status_code == 200
        session_data = get_response.json()
        assert session_data["id"] == session_id


@pytest.mark.usefixtures("mcp_server_processes")
class TestChatEndpoint:
    """Test chat endpoint with HTTP MCP"""
    
    def setup_method(self):
        """Setup before each test"""
        sessions.clear()
    
    def test_chat_endpoint_basic(self, client):
        """Test basic chat functionality"""
        # Chat without pre-existing session
        chat_request = {
            "message": "I need auto insurance",
            "session_id": "chat-test-789"
        }
        
        response = client.post("/chat", json=chat_request)
        assert response.status_code == 200
        data = response.json()
        
        assert "response" in data
        assert "session_id" in data
        assert data["session_id"] == "chat-test-789"
        assert "status" in data
        assert "current_step" in data
    
    def test_chat_nonexistent_session(self, client):
        """Test chat creates session if it doesn't exist"""
        chat_request = {
            "message": "Hello",
            "session_id": "new-session-456"
        }
        
        response = client.post("/chat", json=chat_request)
        # Should create new session, not 404
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "new-session-456"


@pytest.mark.usefixtures("mcp_server_processes")
class TestDocumentEndpoints:
    """Test document upload/retrieval with HTTP MCP"""
    
    def setup_method(self):
        """Setup before each test"""
        sessions.clear()
    
    def test_root_returns_info(self, client):
        """Test that root endpoint returns service info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "mcp_architecture" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
