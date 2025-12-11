#!/usr/bin/env bash
# Start All MCP HTTP Servers

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Starting all MCP HTTP Servers..."
echo "================================"
echo ""

# Start servers in background
echo "Starting PostgreSQL Server (port 8001)..."
python -m mcp_http_servers.postgres_http_server &
PG_PID=$!

echo "Starting Blob Server (port 8002)..."
python -m mcp_http_servers.blob_http_server &
BLOB_PID=$!

echo "Starting Email Server (port 8003)..."
python -m mcp_http_servers.email_http_server &
EMAIL_PID=$!

echo "Starting RAG Server (port 8004)..."
python -m mcp_http_servers.rag_http_server &
RAG_PID=$!

echo ""
echo "All servers started!"
echo "================================"
echo "PostgreSQL Server: http://127.0.0.1:8001/mcp (PID: $PG_PID)"
echo "Blob Server:       http://127.0.0.1:8002/mcp (PID: $BLOB_PID)"
echo "Email Server:      http://127.0.0.1:8003/mcp (PID: $EMAIL_PID)"
echo "RAG Server:        http://127.0.0.1:8004/mcp (PID: $RAG_PID)"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for all background processes
wait
