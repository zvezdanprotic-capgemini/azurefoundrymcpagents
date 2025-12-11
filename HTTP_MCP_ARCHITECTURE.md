# How to Run the KYC System with HTTP MCP Architecture

This guide explains how to run the KYC system with HTTP MCP servers where agents call tools through HTTP.

## Architecture Overview

```
┌──────────────┐
│ main_http.py │ ← FastAPI app (port 8000)
│              │
│ - Chat API   │
│ - Agents     │
└──────┬───────┘
       │
       │ HTTP MCP Client
       │ (langchain-mcp-adapters)
       │
       ├─────────────┬─────────────┬─────────────┐
       │             │             │             │
       v             v             v             v
   ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐
   │Postgres│   │ Blob  │   │ Email │   │  RAG  │
   │ :8001  │   │ :8002 │   │ :8003 │   │ :8004 │
   └───────┘   └───────┘   └───────┘   └───────┘
```

## Key Files

- **`main_http.py`** - Main FastAPI application using HTTP MCP client
- **`main.py`** - OLD version with embedded MCP servers (don't use)
- **`agents/base_http.py`** - Base agent class for HTTP MCP
- **`agents/base.py`** - OLD base class for embedded MCP (not used with HTTP architecture)
- **`agents/*.py`** - All agents now inherit from `BaseKYCAgentHTTP`
- **`mcp_client.py`** - HTTP MCP client wrapper
- **`mcp_servers/*.py`** - Individual MCP servers

## Startup Sequence

### Step 1: Start MCP Servers (Required First!)

The HTTP MCP servers **must** be running before starting the main application.

```bash
# Terminal 1 - PostgreSQL MCP Server
uvicorn mcp_servers.postgres_server:app --host 127.0.0.1 --port 8001

# Terminal 2 - Blob Storage MCP Server
uvicorn mcp_servers.blob_server:app --host 127.0.0.1 --port 8002

# Terminal 3 - Email MCP Server
uvicorn mcp_servers.email_server:app --host 127.0.0.1 --port 8003

# Terminal 4 - RAG MCP Server
uvicorn mcp_servers.rag_server:app --host 127.0.0.1 --port 8004
```

**Or start all at once in background:**

```bash
uvicorn mcp_servers.postgres_server:app --host 127.0.0.1 --port 8001 &
uvicorn mcp_servers.blob_server:app --host 127.0.0.1 --port 8002 &
uvicorn mcp_servers.email_server:app --host 127.0.0.1 --port 8003 &
uvicorn mcp_servers.rag_server:app --host 127.0.0.1 --port 8004 &
```

### Step 2: Verify Servers Are Running

```bash
# Check health endpoints
curl http://127.0.0.1:8001/health  # Should return {"status":"ok","service":"postgres"}
curl http://127.0.0.1:8002/health  # Should return {"status":"ok","service":"blob"}
curl http://127.0.0.1:8003/health  # Should return {"status":"ok","service":"email"}
curl http://127.0.0.1:8004/health  # Should return {"status":"ok","service":"rag"}
```

### Step 3: Start Main Application

```bash
# Terminal 5 - Main FastAPI app with HTTP MCP
uvicorn main_http:app --reload --port 8000
```

### Step 4: Verify Main App

```bash
# Check main app health
curl http://127.0.0.1:8000/

# Check MCP tools loaded
curl http://127.0.0.1:8000/mcp/tools

# Expected: 20 tools from all 4 servers
```

## Testing

### Quick Integration Test

```bash
python test_http_mcp_tools.py
```

Expected output:
```
✅ MCP client initialized
✅ Loaded 20 tools from HTTP MCP servers
✅ Created IntakeAgent (inherits from BaseKYCAgentHTTP)
✅ Agent has access to 3 tools
✅ Agent responded: decision=PASS
```

### Tool Calling Test

```bash
python test_tool_binding.py
```

Expected output:
```
✅ Agent has 3 tools available
✅ LLM with tools bound
✅ SUCCESS: LLM is requesting tool calls!
```

### Full Test Suite

```bash
# Make sure MCP servers are running first!
pytest tests/ -v
```

## Environment Variables

Required in `.env`:

```bash
# Azure OpenAI (for agents)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_DB=kyc_crm
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_STORAGE_CONTAINER_NAME=kyc-documents

# SendGrid Email
SENDGRID_API_KEY=your-api-key
SENDGRID_FROM_EMAIL=noreply@example.com

# Azure AI Search (for RAG)
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-key
AZURE_SEARCH_INDEX_NAME=policy-documents

# MCP Server URLs (optional, defaults shown)
MCP_POSTGRES_URL=http://127.0.0.1:8001/mcp
MCP_BLOB_URL=http://127.0.0.1:8002/mcp
MCP_EMAIL_URL=http://127.0.0.1:8003/mcp
MCP_RAG_URL=http://127.0.0.1:8004/mcp
```

## How Agents Use MCP Tools

### Architecture

1. **Agents** inherit from `BaseKYCAgentHTTP`
2. **Each agent** specifies which tools it needs in `available_tools` property
3. **BaseKYCAgentHTTP** calls `get_mcp_client()` to access HTTP MCP client
4. **MCP Client** loads all tools from HTTP servers via `langchain-mcp-adapters`
5. **Tools are bound** to the LLM using `.bind_tools()`
6. **LLM decides** when to call tools based on the conversation
7. **Tool calls are executed** by calling the LangChain tool (which makes HTTP request to MCP server)

### Example: IntakeAgent

```python
from agents.base_http import BaseKYCAgentHTTP

class IntakeAgent(BaseKYCAgentHTTP):
    @property
    def available_tools(self) -> list:
        return [
            "postgres.get_customer_by_email",  # Maps to postgres__get_customer_by_email
            "postgres.get_customer_history",    # Maps to postgres__get_customer_history
        ]
    
    # When invoked, agent:
    # 1. Gets tools from HTTP MCP client
    # 2. Binds tools to LLM
    # 3. LLM decides if it needs to call tools
    # 4. If yes, tools are called via HTTP
    # 5. Results returned to LLM
    # 6. LLM makes final decision
```

## Troubleshooting

### Issue: "MCP client not initialized"

**Solution:** Make sure MCP servers are running before starting `main_http.py`

### Issue: Connection refused on ports 8001-8004

**Solution:** Start MCP servers first:
```bash
uvicorn mcp_servers.postgres_server:app --port 8001 &
uvicorn mcp_servers.blob_server:app --port 8002 &
uvicorn mcp_servers.email_server:app --port 8003 &
uvicorn mcp_servers.rag_server:app --port 8004 &
```

### Issue: Agents not calling tools

**This is expected behavior!** The LLM only calls tools when it needs external data. To verify tool calling works:

```bash
python test_tool_binding.py
```

This test explicitly asks the LLM to use tools, and it will.

### Issue: "No tools loaded"

**Check:**
1. All 4 MCP servers are running (check health endpoints)
2. MCP client initialized successfully in `main_http.py` lifespan
3. Logs show "MCP client initialized with X tools"

## Key Differences: main.py vs main_http.py

| Feature | main.py (OLD) | main_http.py (NEW) |
|---------|---------------|-------------------|
| MCP Architecture | Embedded servers | HTTP servers |
| Agent Base Class | BaseKYCAgent | BaseKYCAgentHTTP |
| MCP Initialization | PostgresMCPServer() objects | initialize_mcp_client() |
| Tool Access | Direct method calls | HTTP requests |
| Scalability | Monolithic | Distributed |
| Testing | Harder (embedded) | Easier (HTTP mocking) |
| Production Ready | No | Yes |

## Summary

✅ **Always start MCP servers first** on ports 8001-8004
✅ **Then start main_http.py** which connects via HTTP
✅ **Agents automatically access tools** through HTTP MCP client
✅ **LLM decides when to call tools** based on conversation context
✅ **Tool calls execute via HTTP** to the appropriate MCP server

The system is now using the proper HTTP MCP architecture where:
- MCP servers run as independent HTTP services
- Agents connect via `langchain-mcp-adapters`
- Tools are called through standard MCP protocol
- Everything is production-ready and scalable
