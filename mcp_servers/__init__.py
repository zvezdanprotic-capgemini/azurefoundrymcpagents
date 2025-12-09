"""
MCP Servers Module

This module contains Model Context Protocol (MCP) servers that provide
tools for agents to interact with external systems:

- PostgreSQL: Customer CRM data and session state persistence
- Azure Blob: Document storage and retrieval
- Email: Customer notifications
- RAG: Policy compliance via vector search
"""

from mcp_servers.postgres_server import PostgresMCPServer
from mcp_servers.blob_server import BlobMCPServer
from mcp_servers.email_server import EmailMCPServer
from mcp_servers.rag_server import RAGMCPServer

__all__ = [
    "PostgresMCPServer",
    "BlobMCPServer",
    "EmailMCPServer",
    "RAGMCPServer",
]
