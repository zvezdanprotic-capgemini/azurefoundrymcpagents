"""
Unit tests for main_http.py - FastAPI application with HTTP MCP

Tests the main application using HTTP MCP architecture.
Requires HTTP MCP servers to be running (handled by conftest.py fixtures).
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
from fastapi import HTTPException

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_http import app, sessions, load_sessions, save_sessions


@pytest.fixture
def client():
    """Create test client for FastAPI app with lifespan context."""
    with TestClient(app) as c:
        yield c


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
        assert data["service"] == "KYC Orchestrator with HTTP MCP"
        assert data["version"] == "4.0.0"
        assert data["mcp_architecture"] == "HTTP (decoupled servers)"
        assert "mcp_servers" in data
        assert "postgres" in data["mcp_servers"]
        assert "blob" in data["mcp_servers"]
        assert "email" in data["mcp_servers"]
        assert "rag" in data["mcp_servers"]
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "mcp_client" in data
        assert "mcp_tools_loaded" in data
        assert data["status"] == "healthy"
        assert data["mcp_client"] == "connected"
        assert data["mcp_tools_loaded"] > 0
    
    def test_mcp_servers_status(self, client):
        """Test MCP servers status endpoint"""
        response = client.get("/mcp/servers")
        assert response.status_code == 200
        data = response.json()
        assert "servers" in data
        assert "status" in data
        servers = data["servers"]
        assert len(servers) == 4
        assert "postgres" in servers
        assert "blob" in servers
        assert "email" in servers
        assert "rag" in servers
        # Check each server has transport and url
        for server_name in ["postgres", "blob", "email", "rag"]:
            assert "transport" in servers[server_name]
            assert "url" in servers[server_name]
    
    def test_mcp_tools_endpoint(self, client):
        """Test getting MCP tools from all servers"""
        response = client.get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        assert "total_tools" in data
        assert "tools" in data
        assert data["total_tools"] > 0
        assert len(data["tools"]) > 0
        assert data["total_tools"] == len(data["tools"])
        
        # Check tool structure
        tool = data["tools"][0]
        assert "name" in tool
        assert "description" in tool
    
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
