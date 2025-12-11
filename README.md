# Azure AI Foundry KYC Orchestrator with Agentic MCP Integration

A comprehensive KYC (Know Your Customer) orchestrator that uses Azure AI agents with Model Context Protocol (MCP) to enable truly agentic systems capable of autonomously accessing external data, retrieving documents, checking compliance policies, and notifying customers.

## 🎯 Overview

Transform KYC agents from simple LLM callers to truly agentic systems. Agents inherit from `BaseKYCAgentHTTP` and use HTTP MCP servers (independent services). Tools are loaded from HTTP MCP client, and the LLM autonomously decides when to call tools.

**Key Benefit**: Agents are now truly agentic - they autonomously decide when they need external data and call the appropriate MCP tools via HTTP.

## ⚡ Quick Start

**Prerequisites**: Make sure you have all environment variables set in `.env` (see Environment Variables section below)

```bash
# 1. Start all 4 MCP servers (REQUIRED FIRST!)
./start_all_mcp_servers.sh

# 2. Verify servers are running
curl http://127.0.0.1:8001/health  # Should return {"status":"ok"}

# 3. Start main application (HTTP MCP architecture)
uvicorn main_http:app --reload --port 8000

# 4. Test tool calling (optional)
python test_tool_binding.py  # Verify agents can call tools
```

## Features

- **AI-Powered Workflow**: Multiple Azure AI agents handle different stages of the KYC process
- **Agentic MCP Integration**: Agents autonomously call external tools via Model Context Protocol
- **HTTP MCP Architecture**: Independent, scalable MCP servers (ports 8001-8004)
- **20 MCP Tools**: Across 4 specialized servers (PostgreSQL, Blob, Email, RAG)
- **Real-time Chat Interface**: Interactive chat system for customer support
- **Step-by-Step Progress**: Visual workflow tracking with real-time updates
- **Production-Ready Resilience**: Circuit breaker pattern prevents cascading failures (5 failures → 60s timeout)
- **Health Monitoring**: Per-server health status tracking with 5s timeout (`/mcp/health` endpoint)
- **OpenTelemetry Tracing**: Full request tracing with circuit breaker integration
- **Error Handling**: Structured error responses with comprehensive logging
- **RAG-based Compliance**: Policy document search with pgvector embeddings

## System Architecture

```mermaid
graph TD
   FE[React Frontend] --> API[FastAPI Backend main_http.py :8000]
   
   subgraph "Main Application"
      API --> Graph[LangGraph Orchestrator]
      API --> MCP_CLIENT[MCP Client<br/>langchain-mcp-adapters]
      
      Graph --> AGENTS[KYC Agents]
      AGENTS --> I[IntakeAgent<br/>BaseKYCAgentHTTP]
      AGENTS --> V[VerificationAgent<br/>BaseKYCAgentHTTP]
      AGENTS --> E[EligibilityAgent<br/>BaseKYCAgentHTTP]
      AGENTS --> R[RecommendationAgent<br/>BaseKYCAgentHTTP]
      AGENTS --> C[ComplianceAgent<br/>BaseKYCAgentHTTP]
      AGENTS --> A[ActionAgent<br/>BaseKYCAgentHTTP]
      
      AGENTS -.->|get_tools| MCP_CLIENT
   end
   
   subgraph "HTTP MCP Servers - FastMCP + Streamable HTTP"
      MCP_CLIENT -->|HTTP/SSE<br/>:8001/mcp| PG[PostgreSQL MCP Server<br/>6 tools]
      MCP_CLIENT -->|HTTP/SSE<br/>:8002/mcp| BLOB[Blob Storage MCP Server<br/>5 tools]
      MCP_CLIENT -->|HTTP/SSE<br/>:8003/mcp| EMAIL[Email MCP Server<br/>4 tools]
      MCP_CLIENT -->|HTTP/SSE<br/>:8004/mcp| RAG[RAG MCP Server<br/>5 tools]
   end
   
   subgraph "External Systems"
      PG --> DB[(PostgreSQL + pgvector)]
      BLOB --> AZ[Azure Blob Storage]
      RAG --> DB
      RAG --> AOAI[Azure OpenAI Embeddings]
      EMAIL --> SMTP[SendGrid/Email Service]
   end
   
   Graph -.->|State Persist| DB
```

**Key Architecture Features:**
- **HTTP-based MCP**: Servers run as independent HTTP services using FastMCP
- **Streamable HTTP Protocol**: Uses MCP's official protocol with SSE for tool responses
- **Port-based Isolation**: Each server on dedicated port (8001-8004)
- **Client Integration**: `langchain-mcp-adapters` MultiServerMCPClient loads 20 tools from all servers
- **Agentic Tool Calling**: Agents inherit from `BaseKYCAgentHTTP` and LLM decides when to call tools
- **Health Monitoring**: Each server exposes `/health` endpoint for monitoring

## Prerequisites

- Python 3.8+
- Node.js 16+
- PostgreSQL 14+ with pgvector extension
- Azure OpenAI service account
- Azure Blob Storage account
- SendGrid account (for email notifications)

## Installation

### Backend Setup

1. **Clone and navigate to the project**:
   ```bash
   cd azurefoundrymcporchestration
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   
   # Key dependencies include:
   # - fastapi, uvicorn: Web framework
   # - langchain, langgraph: Agent orchestration
   # - langchain-mcp-adapters: MCP client integration
   # - fastmcp: MCP server framework
   # - aiobreaker: Circuit breaker for resilience
   # - opentelemetry-*: Distributed tracing
   ```

4. **Configure environment variables**:
   Create a `.env` file with your Azure credentials and service endpoints:
   ```env
   # PostgreSQL
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=kyc_crm
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   
   # Azure OpenAI (for agents and embeddings)
   AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-api-key
   AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
   AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
   
   # Azure Blob Storage
   AZURE_STORAGE_CONNECTION_STRING=your_connection_string
   AZURE_BLOB_CONTAINER=kyc-documents
   
   # SendGrid Email
   SENDGRID_API_KEY=your_sendgrid_key
   EMAIL_FROM=verified-sender@example.com
   
   # MCP Server URLs (default)
   MCP_POSTGRES_URL=http://127.0.0.1:8001/mcp
   MCP_BLOB_URL=http://127.0.0.1:8002/mcp
   MCP_EMAIL_URL=http://127.0.0.1:8003/mcp
   MCP_RAG_URL=http://127.0.0.1:8004/mcp
   ```

5. **Set up database**:
   ```bash
   # Create database and load schema
   psql -U postgres -c "CREATE DATABASE kyc_crm;"
   psql -U postgres -d kyc_crm -f datamodel/salesforce_core_schema.sql
   psql -U postgres -d kyc_crm -f datamodel/kyc_extensions_schema.sql
   
   # Seed test data
   python seed_crm_data.py
   ```

6. **Start MCP servers** (required before main app):
   ```bash
   ./start_all_mcp_servers.sh
   
   # Or start individually:
   uvicorn mcp_http_servers.postgres_http_server:app --port 8001 &
   uvicorn mcp_http_servers.blob_http_server:app --port 8002 &
   uvicorn mcp_http_servers.email_http_server:app --port 8003 &
   uvicorn mcp_http_servers.rag_http_server:app --port 8004 &
   ```

7. **Verify MCP servers are running**:
   ```bash
   curl http://127.0.0.1:8001/health
   curl http://127.0.0.1:8002/health
   curl http://127.0.0.1:8003/health
   curl http://127.0.0.1:8004/health
   ```

8. **Start the main application**:
   ```bash
   uvicorn main_http:app --reload --port 8000
   ```
   The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```
   The frontend will be available at `http://localhost:3000`

## Usage

1. **Start MCP servers** (in separate terminal or background):
   ```bash
   ./start_all_mcp_servers.sh
   ```

2. **Start main application** (port 8000):
   ```bash
   uvicorn main_http:app --reload --port 8000
   ```

3. **Start frontend** (port 5173):
   ```bash
   cd frontend && npm run dev
   ```

4. **Open the application** at `http://localhost:5173`

5. **Test the system**:
   ```bash
   # Verify MCP tool loading
   curl http://localhost:8000/mcp/tools
   
   # Start a KYC session
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "I need home insurance", "session_id": "test-123"}'
   
   # Check session state
   curl http://localhost:8000/session/test-123
   ```

6. **Upload policy documents** (for RAG/compliance):
   ```bash
   curl -X POST http://localhost:8000/rag/upload \
     -F "file=@policy.pdf" \
     -F "category=underwriting"
   ```

## API Endpoints

### Core Endpoints
- `GET /` - Service info and architecture details
- `GET /health` - Detailed health check (includes MCP client status)
- `POST /chat` - Send chat message and process with agents
- `GET /sessions` - List all active sessions
- `GET /session/{session_id}` - Get session details
- `DELETE /session/{session_id}` - Delete a session

### MCP Endpoints
- `GET /mcp/tools` - List all 20 available MCP tools
- `GET /mcp/servers` - List MCP server configurations
- `GET /mcp/health` - Health status for all MCP servers (per-server monitoring)

### RAG/Policy Management
- `POST /rag/upload` - Upload policy document (PDF/Word)
- `GET /rag/documents` - List indexed policy documents
- `GET /rag/documents/{filename}` - Get document details
- `DELETE /rag/documents/{filename}` - Delete policy document

## MCP Servers

### 1. PostgreSQL MCP Server (Port 8001)
**Purpose**: Access customer CRM data for returning customers

**Tools**:
- `get_customer_by_email` - Lookup contact + account by email
- `get_customer_history` - Get orders, quotes, invoices
- `get_previous_kyc_sessions` - List past KYC sessions
- `save_kyc_session_state` - Persist session state
- `load_kyc_session_state` - Restore session from checkpoint
- `delete_kyc_session` - Delete a session

### 2. Blob Storage MCP Server (Port 8002)
**Purpose**: Store and retrieve customer documents

**Tools**:
- `list_customer_documents` - List all docs for a customer
- `get_document_url` - Get SAS URL for download
- `upload_document` - Store new document
- `get_document_metadata` - Get doc metadata
- `delete_document` - Delete a document

### 3. Email MCP Server (Port 8003)
**Purpose**: Send KYC outcome notifications

**Tools**:
- `send_kyc_approved_email` - Send approval notification
- `send_kyc_pending_email` - Send pending notification
- `send_kyc_rejected_email` - Send rejection notification
- `send_follow_up_email` - Request additional documents

### 4. RAG MCP Server (Port 8004)
**Purpose**: Query compliance policies with vector search

**Tools**:
- `search_policies` - Semantic search over policies
- `get_policy_requirements` - Get requirements for product
- `check_compliance` - Verify customer meets requirements
- `list_policy_categories` - List policy categories
- `delete_policy_document` - Delete policy chunks

## Agent Tool Bindings

| Agent | MCP Tools |
|-------|-----------|
| **IntakeAgent** | `get_customer_by_email`, `get_customer_history` |
| **VerificationAgent** | `list_customer_documents`, `get_document_url` |
| **EligibilityAgent** | `get_customer_history`, `search_policies` |
| **RecommendationAgent** | `get_customer_history`, `search_policies` |
| **ComplianceAgent** | `search_policies`, `check_compliance`, `get_policy_requirements` |
| **ActionAgent** | `send_kyc_approved_email`, `send_kyc_pending_email`, `save_kyc_session_state` |

## Testing

### Automated Tests

```bash
# Run all tests (66 passing, 3 skipped)
source venv/bin/activate
pytest -v

# Test categories:
pytest tests/test_main_http.py -v           # FastAPI endpoints
pytest tests/test_agents_http.py -v         # Agent + MCP integration
pytest tests/test_integration_http.py -v    # End-to-end workflows
pytest tests/test_mcp_servers_http.py -v    # MCP server health checks

# Production improvements tests (17 new tests):
pytest tests/test_circuit_breaker.py -v     # Circuit breaker pattern (5 tests)
pytest tests/test_health_monitoring.py -v   # Health monitoring (6 tests)
pytest tests/test_mcp_tracing.py -v         # OpenTelemetry tracing (6 tests)

# Verify tool calling
python test_tool_binding.py                 # LLM tool call verification
python test_http_mcp_tools.py               # Agent + MCP integration
```

### Connection Testing

Verify external service connectivity before running the system:

```bash
# Run all connection tests
python tests/run_all_connection_tests.py

# Individual tests available:
# - test_azure_openai_connection.py
# - test_azure_embeddings_connection.py
# - test_postgresql_connection.py
# - test_azure_blob_connection.py
# - test_sendgrid_connection.py
```

## Configuration

### Environment Variables (Complete List)

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=kyc_crm
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret

# MCP Server Ports (HTTP endpoints)
MCP_POSTGRES_URL=http://127.0.0.1:8001/mcp
MCP_BLOB_URL=http://127.0.0.1:8002/mcp
MCP_EMAIL_URL=http://127.0.0.1:8003/mcp
MCP_RAG_URL=http://127.0.0.1:8004/mcp

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_BLOB_CONTAINER=kyc-documents

# Azure OpenAI (for agents and embeddings)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# Email (SendGrid)
SENDGRID_API_KEY=SG.xxxxx
EMAIL_FROM=verified-sender@example.com  # Must be verified in SendGrid

# OpenTelemetry (optional)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
ENV=development  # or production
LOG_LEVEL=INFO
```

> [!IMPORTANT]
> For SendGrid, `EMAIL_FROM` must be a **verified sender** in your SendGrid account.
> For Azure Blob Storage, ensure **"Allow storage account key access"** is enabled.

### Frontend Configuration
- `VITE_API_BASE_URL`: Backend API URL (default: http://localhost:8000)

## Development

### Backend Development
```bash
# Install development dependencies
pip install -r requirements.txt

# Start with auto-reload
uvicorn main_http:app --reload --host 0.0.0.0 --port 8000

# Run tests with coverage
pytest --cov=. --cov-report=html
```

### Frontend Development
```bash
cd frontend

# Start development server with hot reload
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Adding New MCP Tools

1. **Add tool to MCP server** (`mcp_http_servers/<server>_http_server.py`):
   ```python
   @mcp.tool()
   async def my_new_tool(param: str) -> dict:
       """Tool description for LLM."""
       # Implementation
       return {"result": "..."}
   ```

2. **Update agent's available_tools** (`agents/<agent>.py`):
   ```python
   @property
   def available_tools(self):
       return [
           "server__existing_tool",
           "server__my_new_tool"  # Add here
       ]
   ```

3. **Restart MCP server** and test:
   ```bash
   # Restart specific server
   pkill -f "postgres_http_server"
   uvicorn mcp_http_servers.postgres_http_server:app --port 8001 &
   
   # Verify tool appears
   curl http://localhost:8000/mcp/tools | grep my_new_tool
   ```

## Troubleshooting

### MCP Servers Not Running

**Issue**: `Connection refused` or `MCP client not initialized`

**Solution**:
```bash
# Check all servers
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
curl http://127.0.0.1:8003/health
curl http://127.0.0.1:8004/health

# Restart all
./start_all_mcp_servers.sh

# Or individually
uvicorn mcp_http_servers.postgres_http_server:app --port 8001 &
# ... etc
```

### Agents Not Calling Tools

**This is expected behavior!** The LLM only calls tools when it needs external data. The agent is smart enough to make decisions based on conversation context.

**To verify tool calling works**:
```bash
python test_tool_binding.py
# Expected: ✅ SUCCESS: LLM is requesting tool calls!
```

### Port Conflicts

**Issue**: `Address already in use`

**Solution**:
```bash
# Find processes using ports
lsof -i :8000 -i :8001 -i :8002 -i :8003 -i :8004

# Kill old servers
pkill -f "uvicorn"

# Restart
./start_all_mcp_servers.sh
uvicorn main_http:app --reload --port 8000
```

### Database Connection Issues

**Issue**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
```bash
# Verify PostgreSQL is running
pg_isready

# Check connection settings in .env
echo $POSTGRES_HOST $POSTGRES_PORT $POSTGRES_DB

# Test connection
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1;"
```

### Azure Blob Storage Access

**Issue**: `AuthorizationPermissionMismatch` or `403 Forbidden`

**Solution**:
- Go to Azure Portal → Storage Account → Settings → Configuration
- Ensure **"Allow storage account key access"** is enabled
- Verify connection string in `.env` is correct
- Test with Azure Storage Explorer

## Production Improvements

### Circuit Breaker Pattern

Protects against cascading failures when MCP servers become unavailable:

- **Library**: `aiobreaker==1.4.0` (async-compatible)
- **Configuration**: Opens after 5 consecutive failures, 60s recovery timeout
- **Features**: 
  - Automatic failure detection and circuit opening
  - Half-open state for gradual recovery
  - Per-client-instance isolation
  - Clear error messages: "Service temporarily unavailable"
  - OpenTelemetry integration for circuit state tracking

### Health Monitoring

Per-server health status tracking:

```bash
# Check all server health
curl http://localhost:8000/mcp/health

# Response:
{
  "postgres": true,
  "blob": true,
  "email": true,
  "rag": false  # Server down
}
```

- **Timeout**: 5 seconds per health check
- **Endpoints**: Each server exposes `/health` endpoint
- **Graceful**: Health check failures don't crash the client

### OpenTelemetry Tracing

Full distributed tracing for debugging and performance analysis:

**Spans**:
- `mcp.get_tools` - Tool discovery operations
- `mcp.tool.{tool_name}` - Individual tool invocations

**Attributes**:
- `mcp.tool.name` - Full tool name
- `mcp.tool.arguments` - Tool arguments
- `mcp.tool.status` - success/error/circuit_open
- `mcp.tool.error` - Error message (when applicable)

**Integration**: Works with standard OpenTelemetry collectors (Jaeger, Zipkin, Datadog, etc.)

For detailed implementation information, see [PRODUCTION_IMPROVEMENTS_SUMMARY.md](./PRODUCTION_IMPROVEMENTS_SUMMARY.md).

## How MCP Works in This System

**MCP (Model Context Protocol)** is an open standard that enables LLM-based agents to interact with external systems through a standardized interface. Instead of hardcoding external API calls, MCP provides a **tool abstraction layer**.

### Architecture Flow

1. **MCP Servers Start**: 4 independent HTTP services on ports 8001-8004
2. **Main App Starts**: Initializes HTTP MCP client, connects to all servers
3. **MCP Client Loads Tools**: 20 tools loaded from all 4 servers via `langchain-mcp-adapters`
4. **User Sends Message**: Via chat API `/chat`
5. **LangGraph Routes**: Message to appropriate agent (e.g., IntakeAgent)
6. **Agent Invoked**: 
   - Inherits from `BaseKYCAgentHTTP`
   - Calls `get_mcp_client()` to get HTTP client
   - Gets all 20 tools, filters to its `available_tools`
   - Binds filtered tools to LLM
7. **LLM Analyzes**: "Do I need external data?"
8. **If YES → Tool Call**:
   - LLM outputs: `{"name": "postgres__get_customer_by_email", "args": {"email": "..."}}`
   - Tool executed via HTTP POST to `:8001/mcp`
   - Result returned as ToolMessage
   - LLM receives result, continues analysis
9. **If NO → Final Decision**: LLM outputs JSON decision (PASS/REVIEW/FAIL)
10. **Response to User**: Decision sent back through API

### Why MCP?

- **Standardized Interface**: Consistent tool calling across all agents
- **Loose Coupling**: Swappable backends, easy mocking in tests
- **Scalability**: Independent HTTP services, can run on different machines
- **Monitoring**: Health endpoints for each service
- **Isolation**: Server crashes don't affect main app

## File Structure

```
├── main_http.py                 # ✅ Main FastAPI app (USE THIS)
├── mcp_client.py                # HTTP MCP client wrapper
├── graph.py                     # LangGraph orchestrator
├── agents/
│   ├── base_http.py             # BaseKYCAgentHTTP (for HTTP MCP)
│   ├── intake.py                # IntakeAgent
│   ├── verification.py          # VerificationAgent
│   ├── eligibility.py           # EligibilityAgent
│   ├── recommendation.py        # RecommendationAgent
│   ├── compliance.py            # ComplianceAgent
│   └── action.py                # ActionAgent
├── mcp_http_servers/
│   ├── postgres_http_server.py  # Port 8001
│   ├── blob_http_server.py      # Port 8002
│   ├── email_http_server.py     # Port 8003
│   └── rag_http_server.py       # Port 8004
├── error_handling/
│   ├── __init__.py              # Error classes and exports
│   ├── middleware.py            # FastAPI error middleware
│   ├── tracing.py               # OpenTelemetry setup
│   └── utils.py                 # Decorators and helpers
├── tests/
│   ├── test_main_http.py        # FastAPI endpoints
│   ├── test_agents_http.py      # Agent + MCP integration
│   ├── test_integration_http.py # End-to-end workflows
│   ├── test_mcp_servers_http.py # MCP server health
│   ├── test_circuit_breaker.py  # Circuit breaker tests (5)
│   ├── test_health_monitoring.py # Health monitoring tests (6)
│   ├── test_mcp_tracing.py      # OpenTelemetry tests (6)
│   └── conftest.py              # pytest fixtures
├── datamodel/
│   ├── salesforce_core_schema.sql
│   └── kyc_extensions_schema.sql
└── frontend/                    # React + TypeScript UI
    └── src/
        ├── components/
        └── services/
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Add tests: `pytest tests/`
5. Ensure all tests pass: `pytest -v`
6. Commit your changes: `git commit -am 'Add feature'`
7. Push to branch: `git push origin feature/your-feature`
8. Submit a pull request

### Development Guidelines

- Follow PEP 8 style guide for Python code
- Add type hints to new functions
- Document new MCP tools in agent docstrings
- Update tests when modifying agents or tools
- Run `pytest` before submitting PRs

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review [MCP documentation](https://modelcontextprotocol.io/)
- Check Azure OpenAI and SendGrid documentation
- Create an issue in the repository

## Additional Resources

- [Model Context Protocol](https://modelcontextprotocol.io/) - Official MCP documentation
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP SDK for Python
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Agent orchestration framework
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/) - Azure AI documentation
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search for PostgreSQL

---

> [!IMPORTANT]
> This architecture uses **FastMCP** (MCP SDK for Python) with **Streamable HTTP transport**. Each server runs as an independent HTTP service, providing better scalability, monitoring, and isolation compared to embedded servers.
>
> **Always use `main_http.py`** - the agents now properly inherit from `BaseKYCAgentHTTP` and will call MCP tools via HTTP when they need external data.