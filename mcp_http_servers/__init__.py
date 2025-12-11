"""
HTTP MCP Servers for KYC System

This package contains FastMCP-based HTTP servers that expose
MCP tools over HTTP/Streamable HTTP protocol.

Each server runs independently on its own port:
- PostgreSQL Server: Port 8001
- Blob Server: Port 8002  
- Email Server: Port 8003
- RAG Server: Port 8004

Use the startup scripts in the root directory to launch servers.
"""
