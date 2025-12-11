#!/usr/bin/env bash
# Start Email MCP HTTP Server on port 8003

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Starting Email MCP HTTP Server on http://127.0.0.1:8003/mcp"
python -m mcp_http_servers.email_http_server
