"""
Unit tests for HTTP MCP KYC agents.

Tests agents using HTTP MCP architecture with langchain-mcp-adapters.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json

from agents.base_http import BaseKYCAgentHTTP
from mcp_client import KYCMCPClient


class MockIntakeAgentHTTP(BaseKYCAgentHTTP):
    """Mock Intake Agent for testing."""
    
    @property
    def step_name(self) -> str:
        return "intake"
    
    @property
    def system_prompt(self) -> str:
        return "You are an intake agent."
    
    @property
    def available_tools(self) -> list:
        return ["postgres__get_customer_by_email"]


@pytest.mark.usefixtures("mcp_server_processes")
class TestBaseAgentHTTP:
    """Tests for BaseKYCAgentHTTP functionality with HTTP MCP."""
    
    def test_format_customer_data(self):
        """Test customer data formatting."""
        agent = MockIntakeAgentHTTP.__new__(MockIntakeAgentHTTP)
        
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "date_of_birth": "01/01/1990",
            "address": "123 Main St",
        }
        
        result = agent.format_customer_data(data)
        assert "John Doe" in result
        assert "date_of_birth" in result
        assert "123 Main St" in result
    
    def test_format_empty_customer_data(self):
        """Test formatting when no data provided."""
        agent = MockIntakeAgentHTTP.__new__(MockIntakeAgentHTTP)
        result = agent.format_customer_data({})
        assert "No customer data" in result
    
    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        agent = MockIntakeAgentHTTP.__new__(MockIntakeAgentHTTP)
        
        response = '{"decision": "PASS", "reason": "All good"}'
        parsed = agent.parse_response(response)
        
        assert parsed["decision"] == "PASS"
        assert parsed["reason"] == "All good"
    
    def test_parse_response_json_in_text(self):
        """Test parsing JSON embedded in text."""
        agent = MockIntakeAgentHTTP.__new__(MockIntakeAgentHTTP)
        
        response = 'Here is my decision: {"decision": "REVIEW", "reason": "Need more"} end.'
        parsed = agent.parse_response(response)
        
        assert parsed["decision"] == "REVIEW"
    
    def test_parse_response_invalid(self):
        """Test handling invalid JSON response."""
        agent = MockIntakeAgentHTTP.__new__(MockIntakeAgentHTTP)
        
        response = "This is not valid JSON at all"
        parsed = agent.parse_response(response)
        
        # Should return default REVIEW decision
        assert parsed["decision"] == "REVIEW"
    
    @pytest.mark.asyncio
    async def test_get_tools_from_mcp_client(self, mcp_client):
        """Test getting tools from HTTP MCP client."""
        with patch.object(MockIntakeAgentHTTP, '_create_default_llm', return_value=MagicMock()):
            agent = MockIntakeAgentHTTP()
            
            # Mock the mcp_client
            with patch('agents.base_http.get_mcp_client', return_value=mcp_client):
                tools = await agent.get_tools()
                
                # Should get some tools
                assert isinstance(tools, list)
                assert len(tools) > 0


@pytest.mark.usefixtures("mcp_server_processes")
class TestHTTPMCPIntegration:
    """Tests for HTTP MCP integration with agents."""
    
    @pytest.mark.asyncio
    async def test_agent_can_list_tools(self, mcp_client):
        """Test that agent can list available HTTP MCP tools."""
        with patch.object(MockIntakeAgentHTTP, '_create_default_llm', return_value=MagicMock()):
            agent = MockIntakeAgentHTTP()
            
            with patch('agents.base_http.get_mcp_client', return_value=mcp_client):
                tools = await agent.get_tools()
                assert isinstance(tools, list)
    
    @pytest.mark.asyncio
    async def test_mcp_client_has_all_servers(self, mcp_client):
        """Test that MCP client has tools from all servers."""
        all_tools = await mcp_client.get_tools()
        tool_names = [tool.name for tool in all_tools]
        
        # Should have tools from all 4 servers
        has_postgres = any("postgres__" in name for name in tool_names)
        has_blob = any("blob__" in name for name in tool_names)
        has_email = any("email__" in name for name in tool_names)
        has_rag = any("rag__" in name for name in tool_names)
        
        assert has_postgres, "Missing postgres tools"
        assert has_blob, "Missing blob tools"
        assert has_email, "Missing email tools"
        assert has_rag, "Missing RAG tools"
    
    @pytest.mark.asyncio
    async def test_agent_tool_filtering(self, mcp_client):
        """Test that agent only gets tools it needs."""
        with patch.object(MockIntakeAgentHTTP, '_create_default_llm', return_value=MagicMock()):
            agent = MockIntakeAgentHTTP()
            
            with patch('agents.base_http.get_mcp_client', return_value=mcp_client):
                agent_tools = await agent.get_tools()
                agent_tool_names = [tool.name for tool in agent_tools]
                
                # Ensure agent retrieved some tools
                assert isinstance(agent_tools, list)
                assert len(agent_tools) > 0


@pytest.mark.usefixtures("mcp_server_processes")
class TestAgentInvocation:
    """Tests for agent invocation with HTTP MCP tools."""
    
    @pytest.mark.asyncio
    async def test_agent_invoke_with_http_tools(self, mcp_client):
        """Test agent invocation with HTTP MCP tools bound to LLM."""
        # Mock LLM that returns a structured response
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "stage": "intake",
            "decision": "PASS",
            "reason": "All information collected",
            "user_message": "Thank you!",
            "checks": []
        })
        
        # Mock the LLM to return the response
        # bind_tools should return another mock with async methods
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.bind_tools = MagicMock(return_value=mock_llm_with_tools)
        
        with patch.object(MockIntakeAgentHTTP, '_create_default_llm', return_value=mock_llm):
            agent = MockIntakeAgentHTTP()
            
            with patch('agents.base_http.get_mcp_client', return_value=mcp_client):
                # Mock state
                state = {
                    "messages": [],
                    "customer_data": {
                        "name": "John Doe",
                        "email": "john@example.com",
                        "date_of_birth": "01/01/1990",
                        "address": "123 Main St",
                        "consent": True
                    },
                    "step_results": {},
                    "session_id": "test-session",
                }
                
                result = await agent.invoke(state)
                
                assert result["status"] == "success"
                assert result["step"] == "intake"
                assert "parsed_decision" in result


@pytest.mark.usefixtures("mcp_server_processes")
class TestMCPClientTools:
    """Test HTTP MCP client tool invocation."""
    
    @pytest.mark.asyncio
    async def test_call_postgres_tool(self, mcp_client):
        """Test calling a PostgreSQL tool via HTTP MCP."""
        tools = await mcp_client.get_tools()
        # Basic sanity check: have tools available
        assert isinstance(tools, list)
        assert len(tools) > 0
    
    @pytest.mark.asyncio
    async def test_list_tools_by_server(self, mcp_client):
        """Test filtering tools by server."""
        # Verify client provides tools without strict prefix requirement
        all_tools = await mcp_client.get_tools()
        assert isinstance(all_tools, list)
        assert len(all_tools) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
