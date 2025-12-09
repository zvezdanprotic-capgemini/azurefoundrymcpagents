import base64
import json
import pytest
from fastapi.testclient import TestClient

# Import app from main
import main
from main import app, sessions

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_session(monkeypatch):
    # Create a dummy session
    session_id = "test-session-123"
    sessions[session_id] = {
        "customer": {"name": "Alice", "email": "alice@example.com", "insurance_needs": "auto"},
        "step": "intake",
        "status": "in_progress",
        "chat_history": [],
        "step_results": {},
        "thread_ids": {}
    }

    # Mock Postgres MCP server
    # Replace MCP servers on the main module with dummies

    class DummyResult:
        def __init__(self, success=True, data=None, error=None):
            self.success = success
            self.data = data or {}
            self.error = error

    async def mock_call_tool_postgres(tool_name, args):
        if tool_name == "get_customer_by_email":
            return DummyResult(success=True, data={
                "found": True,
                "contact": {"id": 101},
                "account": {"id": 202, "name": "Acme"}
            })
        elif tool_name == "get_previous_kyc_sessions":
            return DummyResult(success=True, data={
                "sessions": [{"id": "abc", "status": "complete", "current_step": "action"}]
            })
        return DummyResult(success=False, error=f"Unknown tool: {tool_name}")

    async def mock_call_tool_blob(tool_name, args):
        if tool_name == "list_customer_documents":
            return DummyResult(success=True, data={
                "account_id": args["account_id"],
                "document_count": 1,
                "documents": [{
                    "name": f"customers/Customer{args['account_id']}/id/passport.pdf",
                    "size": 12345,
                    "metadata": {"document_type": "id"}
                }]
            })
        elif tool_name == "upload_document":
            return DummyResult(success=True, data={
                "uploaded": True,
                "blob_path": f"customers/Customer{args['account_id']}/other/{args['filename']}",
                "size": len(base64.b64decode(args["content_base64"]))
            })
        return DummyResult(success=False, error=f"Unknown tool: {tool_name}")

    class DummyPostgres:
        async def call_tool(self, tool_name, args):
            return await mock_call_tool_postgres(tool_name, args)

    class DummyBlob:
        async def call_tool(self, tool_name, args):
            return await mock_call_tool_blob(tool_name, args)

    monkeypatch.setattr(main, "mcp_postgres", DummyPostgres())
    monkeypatch.setattr(main, "mcp_blob", DummyBlob())

    yield session_id

    # Cleanup
    sessions.pop(session_id, None)


def test_panel_data_endpoint(setup_session):
    session_id = setup_session
    resp = client.get(f"/session/{session_id}/panel-data")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session"]["session_id"] == session_id
    assert data["crm"]["found"] is True
    assert data["documents"]["document_count"] == 1
    assert "previous_sessions" in data


def test_list_session_documents(setup_session):
    session_id = setup_session
    resp = client.get(f"/session/{session_id}/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert docs["document_count"] == 1
    assert len(docs["documents"]) == 1


def test_upload_session_document(setup_session):
    session_id = setup_session
    content = b"hello world"
    files = {"file": ("note.txt", content, "text/plain")}
    resp = client.post(f"/session/{session_id}/documents/upload", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "uploaded"
    assert data["uploaded"] is True
    assert data["size"] == len(content)
