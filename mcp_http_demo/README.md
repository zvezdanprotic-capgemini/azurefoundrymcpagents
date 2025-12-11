
# MCP HTTP Demo (Server + Client + LangGraph Agent)

This zip contains a minimal end-to-end setup:

- **server/http_math_server.py** — MCP server over **Streamable HTTP** exposing `add` and `multiply` tools.
- **client/http_mcp_client.py** — MCP client connecting to the server via HTTP and calling tools.
- **agent/langgraph_agent_http.py** — LangGraph agent using `langchain-mcp-adapters` to load the server's tools.

## Quick start

1) **Start the HTTP MCP server**
```bash
cd server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python http_math_server.py
# Server listens on http://127.0.0.1:8000/mcp
```

2) **Test with the standalone MCP client**
```bash
cd ../client
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python http_mcp_client.py
```

3) **Run the LangGraph agent that consumes MCP tools**
```bash
cd ../agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=YOUR_KEY
python langgraph_agent_http.py
```

## Notes

- The MCP server uses **Streamable HTTP** (`/mcp`) with `json_response=True`, a simple mode that avoids SSE streams.
- The client uses `mcp.client.streamable_http.streamablehttp_client` to connect to the HTTP endpoint.
- The agent uses `MultiServerMCPClient` (langchain-mcp-adapters) with `transport: "http"` to load tools.

## Files

- `server/requirements.txt`: minimal dependencies for the server
- `client/requirements.txt`: minimal dependencies for the client
- `agent/requirements.txt`: dependencies for LangChain/LangGraph and MCP adapters

## Security & production

These examples are intended for local development. For production, consider authentication, CORS, and SSE streaming behavior.
