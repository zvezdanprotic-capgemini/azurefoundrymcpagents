"""
HTTP MCP Client for KYC System

This module provides a client that connects to HTTP MCP servers
using the standard MCP protocol with langchain-mcp-adapters.

The client manages connections to multiple MCP servers and provides
a unified interface for agents to call tools.
"""
import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger("kyc.mcp_client")


class KYCMCPClient:
    """
    Client for connecting to HTTP MCP servers.
    
    This client manages connections to PostgreSQL, Blob, Email, and RAG servers,
    all running as separate HTTP services.
    """
    
    def __init__(
        self,
        postgres_url: str = "http://127.0.0.1:8001/mcp",
        blob_url: str = "http://127.0.0.1:8002/mcp",
        email_url: str = "http://127.0.0.1:8003/mcp",
        rag_url: str = "http://127.0.0.1:8004/mcp"
    ):
        """
        Initialize MCP client with server URLs.
        
        Args:
            postgres_url: URL for PostgreSQL MCP server
            blob_url: URL for Blob Storage MCP server
            email_url: URL for Email MCP server
            rag_url: URL for RAG MCP server
        """
        self.server_config = {
            "postgres": {
                "transport": "streamable_http",
                "url": postgres_url,
            },
            "blob": {
                "transport": "streamable_http",
                "url": blob_url,
            },
            "email": {
                "transport": "streamable_http",
                "url": email_url,
            },
            "rag": {
                "transport": "streamable_http",
                "url": rag_url,
            }
        }
        
        self._client: Optional[MultiServerMCPClient] = None
        self._tools: Optional[List] = None
    
    async def initialize(self):
        """Initialize connection to all MCP servers."""
        logger.info("Initializing HTTP MCP client connections...")
        self._client = MultiServerMCPClient(self.server_config)
        raw_tools = await self._client.get_tools()
        # Normalize tool names with server prefixes so tests and agents can target specific servers
        server_tool_index = {
            "postgres": {
                "get_customer_by_email",
                "get_customer_history",
                "get_previous_kyc_sessions",
                "save_kyc_session_state",
                "load_kyc_session_state",
                "delete_kyc_session",
            },
            "blob": {
                "list_customer_documents",
                "get_document_url",
                "upload_document",
                "get_document_metadata",
                "delete_document",
            },
            "email": {
                "send_kyc_approved_email",
                "send_kyc_pending_email",
                "send_kyc_rejected_email",
            },
            "rag": {
                "search_policies",
                "get_policy_requirements",
                "check_compliance",
                "list_policy_categories",
                "delete_policy_document",
            },
        }
        prefixed_tools = []
        for tool in raw_tools:
            name = getattr(tool, "name", "")
            base = name.split("__")[-1] if "__" in name else name
            # Find server by base name
            server_match = None
            for server, names in server_tool_index.items():
                if base in names:
                    server_match = server
                    break
            if server_match and not name.startswith(server_match + "__"):
                # Mutate name to include server prefix for test consistency
                try:
                    setattr(tool, "name", f"{server_match}__{base}")
                except Exception:
                    pass
            prefixed_tools.append(tool)
        self._tools = prefixed_tools
        logger.info(f"Connected to MCP servers. Loaded {len(self._tools)} tools.")
    
    async def get_tools(self) -> List:
        """Get all available tools from connected servers."""
        if self._tools is None:
            await self.initialize()
        return self._tools
    
    def get_tools_for_server(self, server_name: str) -> List:
        """Get tools for a specific server."""
        if self._tools is None:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        return [tool for tool in self._tools if getattr(tool, "name", "").startswith(f"{server_name}__")]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on an MCP server.
        
        Args:
            tool_name: Full tool name (e.g., "postgres__get_customer_by_email")
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        if self._client is None:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        # Find the tool
        tool = next((t for t in self._tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # Invoke the tool
        result = await tool.ainvoke(arguments)
        return result
    
    async def close(self):
        """Close connections to all MCP servers."""
        if self._client:
            # MultiServerMCPClient handles cleanup
            logger.info("Closed MCP client connections")


# Global client instance (initialized at app startup)
_mcp_client: Optional[KYCMCPClient] = None


def initialize_mcp_client(
    postgres_url: str = "http://127.0.0.1:8001/mcp",
    blob_url: str = "http://127.0.0.1:8002/mcp",
    email_url: str = "http://127.0.0.1:8003/mcp",
    rag_url: str = "http://127.0.0.1:8004/mcp"
) -> KYCMCPClient:
    """
    Initialize the global MCP client.
    
    Call this at application startup before using agents.
    """
    global _mcp_client
    _mcp_client = KYCMCPClient(postgres_url, blob_url, email_url, rag_url)
    return _mcp_client


def get_mcp_client() -> KYCMCPClient:
    """Get the global MCP client instance."""
    if _mcp_client is None:
        raise RuntimeError("MCP client not initialized. Call initialize_mcp_client() first.")
    return _mcp_client
