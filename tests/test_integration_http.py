"""
End-to-end integration tests for HTTP MCP architecture

Tests the full system with HTTP MCP servers running independently.
"""
import pytest
import uuid
from fastapi.testclient import TestClient

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_http import app


@pytest.fixture
def client():
    """Create test client for FastAPI app with lifespan context."""
    with TestClient(app) as c:
        yield c


@pytest.mark.usefixtures("mcp_server_processes")
@pytest.mark.integration
def test_health_check(client):
    """Test that main_http health endpoint works."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "mcp_client" in data


@pytest.mark.usefixtures("mcp_server_processes")
@pytest.mark.integration
def test_mcp_architecture_info(client):
    """Test that root endpoint shows HTTP MCP architecture info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["mcp_architecture"] == "HTTP (decoupled servers)"
    assert "mcp_servers" in data


@pytest.mark.usefixtures("mcp_server_processes")
@pytest.mark.integration
def test_mcp_servers_accessible(client):
    """Test that all MCP servers are accessible."""
    response = client.get("/mcp/servers")
    assert response.status_code == 200
    data = response.json()
    
    servers = data["servers"]
    assert len(servers) == 4
    assert "postgres" in servers
    assert "blob" in servers
    assert "email" in servers
    assert "rag" in servers


@pytest.mark.usefixtures("mcp_server_processes")
@pytest.mark.integration
def test_mcp_tools_loaded(client):
    """Test that MCP tools are loaded from all servers."""
    response = client.get("/mcp/tools")
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_tools"] > 0
    
    # Check we have tools
    assert len(data["tools"]) > 0


@pytest.mark.usefixtures("mcp_server_processes")
@pytest.mark.integration
def test_end_to_end_session_flow(client):
    """Test complete session flow with HTTP MCP."""
    # 1. Create Session via chat
    chat_request = {
        "message": "I need auto insurance. I'm HTTP MCP Test User at httpmcp@example.com",
        "session_id": "integration-test-session"
    }
    response = client.post("/chat", json=chat_request)
    assert response.status_code == 200
    session_data = response.json()
    session_id = session_data["session_id"]
    assert session_id == "integration-test-session"
    
    print(f"\n✓ Session created: {session_id}")

    # 2. Get Session Details
    response = client.get(f"/session/{session_id}")
    assert response.status_code == 200
    session_details = response.json()
    assert session_details["id"] == session_id
    assert "status" in session_details
    assert "current_step" in session_details
    
    print(f"✓ Session retrieved: step={session_details['current_step']}")

    # 3. Chat again in same session
    chat_request2 = {
        "message": "I live at 456 Oak Ave, Boston, MA 02101",
        "session_id": session_id
    }
    response = client.post("/chat", json=chat_request2)
    
    # May succeed or fail depending on LLM/MCP configuration
    if response.status_code == 200:
        chat_response = response.json()
        assert "response" in chat_response
        assert "current_step" in chat_response
        print(f"✓ Chat successful: {chat_response['current_step']}")
    else:
        print(f"⚠ Chat failed (expected in some test environments): {response.status_code}")

    # 4. List Sessions
    response = client.get("/sessions")
    assert response.status_code == 200
    sessions_data = response.json()
    assert "sessions" in sessions_data
    
    # Check our session is in the list
    session_ids = [s["id"] for s in sessions_data["sessions"]]
    assert session_id in session_ids
    
    print(f"✓ Session list contains {session_id}")


@pytest.mark.usefixtures("mcp_server_processes")
@pytest.mark.integration
def test_workflow_steps_endpoint(client):
    """Test that MCP tools are available."""
    # Test tools endpoint
    response = client.get("/mcp/tools")
    assert response.status_code == 200
    data = response.json()
    
    assert "total_tools" in data
    assert data["total_tools"] > 0


@pytest.mark.usefixtures("mcp_server_processes")
@pytest.mark.integration
def test_session_not_found(client):
    """Test handling of non-existent session."""
    fake_session_id = str(uuid.uuid4())
    response = client.get(f"/session/{fake_session_id}")
    assert response.status_code == 404


@pytest.mark.usefixtures("mcp_server_processes")
@pytest.mark.integration
def test_chat_with_invalid_session(client):
    """Test chat creates new session if ID doesn't exist."""
    fake_session_id = str(uuid.uuid4())
    chat_msg = {
        "message": "Hello",
        "session_id": fake_session_id
    }
    response = client.post("/chat", json=chat_msg)
    # Should create new session, not 404
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == fake_session_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
