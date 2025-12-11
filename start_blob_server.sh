#!/usr/bin/env bash
# Start Blob Storage MCP HTTP Server on port 8002

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Starting Blob Storage MCP HTTP Server on http://127.0.0.1:8002/mcp"
python -m mcp_http_servers.blob_http_server
