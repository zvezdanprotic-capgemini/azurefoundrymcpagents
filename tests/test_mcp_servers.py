"""
Unit tests for MCP servers.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json

from mcp_servers.base import BaseMCPServer, ToolResult, get_env_or_default
from mcp_servers.postgres_server import PostgresMCPServer
from mcp_servers.blob_server import BlobMCPServer
from mcp_servers.email_server import EmailMCPServer
from mcp_servers.rag_server import RAGMCPServer


class TestToolResult:
    """Tests for ToolResult data class."""
    
    def test_success_result(self):
        result = ToolResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
    
    def test_error_result(self):
        result = ToolResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"
    
    def test_to_dict(self):
        result = ToolResult(success=True, data={"test": 123})
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == {"test": 123}
        assert "error" not in d


class TestPostgresMCPServer:
    """Tests for PostgresMCPServer."""
    
    def test_name(self):
        server = PostgresMCPServer()
        assert server.name == "postgres"
    
    def test_get_tools(self):
        server = PostgresMCPServer()
        tools = server.get_tools()
        
        tool_names = [t["name"] for t in tools]
        assert "get_customer_by_email" in tool_names
        assert "get_customer_history" in tool_names
        assert "save_kyc_session_state" in tool_names
        assert "load_kyc_session_state" in tool_names
    
    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        server = PostgresMCPServer()
        result = await server.call_tool("nonexistent_tool", {})
        assert result.success is False
        assert "Unknown tool" in result.error


class TestBlobMCPServer:
    """Tests for BlobMCPServer."""
    
    def test_name(self):
        server = BlobMCPServer()
        assert server.name == "blob"
    
    def test_get_tools(self):
        server = BlobMCPServer()
        tools = server.get_tools()
        
        tool_names = [t["name"] for t in tools]
        assert "list_customer_documents" in tool_names
        assert "get_document_url" in tool_names
        assert "upload_document" in tool_names
        assert "get_document_metadata" in tool_names
    
    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        server = BlobMCPServer()
        result = await server.call_tool("nonexistent_tool", {})
        assert result.success is False


class TestEmailMCPServer:
    """Tests for EmailMCPServer."""
    
    def test_name(self):
        server = EmailMCPServer()
        assert server.name == "email"
    
    def test_get_tools(self):
        server = EmailMCPServer()
        tools = server.get_tools()
        
        tool_names = [t["name"] for t in tools]
        assert "send_kyc_approved_email" in tool_names
        assert "send_kyc_pending_email" in tool_names
        assert "send_kyc_rejected_email" in tool_names
        assert "send_follow_up_email" in tool_names
    
    @pytest.mark.asyncio
    async def test_mock_email_send(self):
        """Test email sending in mock mode (no email configured)."""
        server = EmailMCPServer()
        
        result = await server.call_tool("send_kyc_approved_email", {
            "to_email": "test@example.com",
            "customer_name": "John Doe"
        })
        
        # Should succeed (either mock or real mode depending on config)
        assert result.success is True
        assert "sent" in result.data
        assert result.data["sent"] is True
        assert result.data["to"] == "test@example.com"


class TestRAGMCPServer:
    """Tests for RAGMCPServer."""
    
    def test_name(self):
        server = RAGMCPServer()
        assert server.name == "rag"
    
    def test_get_tools(self):
        server = RAGMCPServer()
        tools = server.get_tools()
        
        tool_names = [t["name"] for t in tools]
        assert "search_policies" in tool_names
        assert "get_policy_requirements" in tool_names
        assert "check_compliance" in tool_names
        assert "list_policy_categories" in tool_names
    
    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        server = RAGMCPServer()
        result = await server.call_tool("nonexistent_tool", {})
        assert result.success is False


class TestGetEnvOrDefault:
    """Tests for environment variable helpers."""
    
    def test_get_env_default(self):
        result = get_env_or_default("NONEXISTENT_VAR_12345", "default_value")
        assert result == "default_value"
    
    def test_get_env_from_env(self):
        import os
        os.environ["TEST_VAR_MCP"] = "test_value"
        try:
            result = get_env_or_default("TEST_VAR_MCP", "default")
            assert result == "test_value"
        finally:
            del os.environ["TEST_VAR_MCP"]
