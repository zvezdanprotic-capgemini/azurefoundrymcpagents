#!/usr/bin/env bash
# Start PostgreSQL MCP HTTP Server on port 8001

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Starting PostgreSQL MCP HTTP Server on http://127.0.0.1:8001/mcp"
python -m mcp_http_servers.postgres_http_server
