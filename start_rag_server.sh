#!/usr/bin/env bash
# Start RAG MCP HTTP Server on port 8004

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Starting RAG MCP HTTP Server on http://127.0.0.1:8004/mcp"
python -m mcp_http_servers.rag_http_server
