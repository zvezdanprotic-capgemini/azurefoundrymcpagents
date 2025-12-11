"""
Main FastAPI Application with HTTP MCP Client

This version uses HTTP MCP servers running as separate processes.
Each MCP server runs on its own port and agents connect via HTTP.

Before running this application:
1. Start all MCP servers: ./start_all_mcp_servers.sh
2. Verify servers are running on ports 8001-8004
3. Then start this FastAPI app: uvicorn main_http:app --reload --port 8000
"""
import os
import json
import uuid
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

# Import HTTP MCP Client
from mcp_client import initialize_mcp_client, get_mcp_client
from graph import app_graph

# Import error handling and tracing
from error_handling import (
    setup_app,
    ErrorHandlingConfig,
    handle_errors,
    trace_function,
    get_tracer,
    KYCError,
    ServiceUnavailableError,
    ValidationError,
    NotFoundError
)

# Load environment variables
load_dotenv()

# Configure application
SERVICE_NAME = "kyc-orchestrator"
VERSION = "4.0.0"

# Set up logger
import logging
logger = logging.getLogger(SERVICE_NAME)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and cleanup HTTP MCP client."""
    app.state.logger = logger
    logger.info("Initializing HTTP MCP client...")
    
    try:
        # Initialize HTTP MCP client (connects to servers on ports 8001-8004)
        mcp_client = initialize_mcp_client(
            postgres_url=os.getenv("MCP_POSTGRES_URL", "http://127.0.0.1:8001/mcp"),
            blob_url=os.getenv("MCP_BLOB_URL", "http://127.0.0.1:8002/mcp"),
            email_url=os.getenv("MCP_EMAIL_URL", "http://127.0.0.1:8003/mcp"),
            rag_url=os.getenv("MCP_RAG_URL", "http://127.0.0.1:8004/mcp"),
        )
        
        # Initialize connection
        await mcp_client.initialize()
        app.state.mcp_client = mcp_client
        logger.info("HTTP MCP client initialized successfully")
        
        yield
        
        # Cleanup
        logger.info("Shutting down HTTP MCP client...")
        await mcp_client.close()
        logger.info("HTTP MCP client shut down")
        
    except Exception as e:
        logger.error("Failed to initialize MCP client", exc_info=True)
        raise ServiceUnavailableError("MCP Service", cause=e)

# Create FastAPI app
app = FastAPI(
    title=f"Azure AI Agents {SERVICE_NAME}", 
    version=VERSION,
    description="KYC system with HTTP MCP servers for true service decoupling",
    lifespan=lifespan
)

# Configure error handling and tracing
config = ErrorHandlingConfig(
    service_name=SERVICE_NAME,
    environment=os.getenv("ENV", "development"),
    otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    enable_tracing=True,
    enable_error_handling=True
)

# Set up error handling, tracing, and request ID middleware
app = setup_app(app, config)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=json.loads(os.getenv("ALLOWED_ORIGINS", "[\"http://localhost:3000\", \"http://localhost:5173\"]")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session persistence
SESSIONS_FILE = Path("sessions.json")


@trace_function()
def load_sessions() -> Dict[str, Any]:
    """Load sessions from file."""
    try:
        if SESSIONS_FILE.exists():
            with open(SESSIONS_FILE, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        app.state.logger.error("Failed to load sessions", exc_info=True)
        return {}


@trace_function()
def save_sessions(sessions: Dict[str, Any]) -> None:
    """Save sessions to file."""
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        app.state.logger.error("Failed to save sessions", exc_info=True)
        raise ServiceUnavailableError("Session Storage", cause=e)


# Initialize sessions
sessions = load_sessions()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    status: str
    current_step: str
    customer: Dict[str, Any]


@app.get("/")
@handle_errors()
@trace_function()
async def root():
    """Health check endpoint."""
    return {
        "service": f"{SERVICE_NAME} with HTTP MCP",
        "version": VERSION,
        "status": "running",
        "mcp_architecture": "HTTP (decoupled servers)",
        "mcp_servers": {
            "postgres": os.getenv("MCP_POSTGRES_URL", "http://127.0.0.1:8001/mcp"),
            "blob": os.getenv("MCP_BLOB_URL", "http://127.0.0.1:8002/mcp"),
            "email": os.getenv("MCP_EMAIL_URL", "http://127.0.0.1:8003/mcp"),
            "rag": os.getenv("MCP_RAG_URL", "http://127.0.0.1:8004/mcp"),
        }
    }


@app.get("/health")
@handle_errors()
@trace_function()
async def health():
    """Detailed health check including MCP server connectivity."""
    mcp_client = get_mcp_client()
    
    # Check if MCP client is connected
    if not mcp_client or not hasattr(mcp_client, 'is_connected') or not mcp_client.is_connected():
        from error_handling import KYCError, ErrorCode
        raise KYCError(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="MCP client is not connected",
            status_code=503,
            details={"service": "MCP Client"}
        )
    
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": VERSION,
        "mcp_connected": True,
        "mcp_client": "connected"
    }


@app.post("/chat", response_model=ChatResponse)
@handle_errors()
@trace_function(attributes={"component": "chat_endpoint"})
async def chat(request: ChatRequest):
    """
    Main chat endpoint for KYC workflow.
    
    Uses LangGraph orchestrator with HTTP MCP clients.
    """
    # Get or create session with trace context
    session_id = request.session_id or str(uuid.uuid4())
    
    with get_tracer(__name__).start_as_current_span("process_chat") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("has_session_id", bool(request.session_id))
        
        if session_id not in sessions:
            sessions[session_id] = {
                "id": session_id,
                "status": "active",
                "customer": {},
                "messages": [],
                "current_step": "intake",
                "step_results": {}
            }
        
        session = sessions[session_id]
        
        # Add user message to history
        session["messages"].append({
            "role": "user",
            "content": request.message,
            "timestamp": str(asyncio.get_event_loop().time())
        })
        
        # Prepare graph input
        graph_input = {
            "messages": [HumanMessage(content=request.message)],
            "customer_data": session["customer"],
            "next_step": session["current_step"],
            "step_results": session["step_results"],
            "session_id": session_id,
            "thread_ids": {},
            "final_response": "",
            "routing_signal": "GO",
            "mcp_tool_calls": []
        }
        
        # Run graph (agents use HTTP MCP client)
        result = await app_graph.ainvoke(graph_input)
        
        # Extract response
        ai_response = result.get("final_response", "I'm processing your request...")
        
        # Update session
        session["customer"] = result.get("customer_data", {})
        session["current_step"] = result.get("next_step", "intake")
        session["step_results"] = result.get("step_results", {})
        session["messages"].append({
            "role": "assistant",
            "content": ai_response,
            "timestamp": str(asyncio.get_event_loop().time())
        })
        
        # Save sessions
        save_sessions(sessions)
        
        # Add trace attributes
        span.set_attribute("response_length", len(ai_response))
        span.set_attribute("current_step", session["current_step"])
        
        return ChatResponse(
            response=ai_response,
            session_id=session_id,
            status=session["status"],
            current_step=session["current_step"],
            customer=session["customer"]
        )


@app.get("/sessions")
@handle_errors()
@trace_function()
async def list_sessions():
    """List all active sessions."""
    return {"sessions": list(sessions.values())}


@app.get("/session/{session_id}")
@handle_errors()
@trace_function(attributes={"component": "get_session"})
async def get_session(session_id: str):
    """Get session details."""
    if session_id not in sessions:
        raise NotFoundError(resource="Session", id=session_id, message="Session not found")
    return sessions[session_id]


@app.delete("/session/{session_id}")
@handle_errors()
@trace_function(attributes={"component": "delete_session"})
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id in sessions:
        del sessions[session_id]
        save_sessions(sessions)
        return {"deleted": True, "session_id": session_id}
    raise NotFoundError(resource="Session", id=session_id, message="Session not found")


@app.get("/mcp/tools")
@handle_errors()
@trace_function(attributes={"component": "list_mcp_tools"})
async def list_mcp_tools():
    """List all available MCP tools from HTTP servers."""
    mcp_client = get_mcp_client()
    if not mcp_client or not hasattr(mcp_client, 'get_tools'):
        raise ServiceUnavailableError("MCP Client", "MCP client is not available")
        
    tools = await mcp_client.get_tools()
    
    # Serialize tools to dict format
    tools_data = []
    for tool in tools:
        tool_info = {
            "name": tool.name,
            "description": tool.description,
        }
        # Add input schema if available
        if hasattr(tool, 'args_schema') and tool.args_schema:
            try:
                tool_info["input_schema"] = tool.args_schema.model_json_schema()
            except:
                pass
        tools_data.append(tool_info)
    
    return {
        "total_tools": len(tools_data),
        "tools": tools_data
    }


@app.get("/mcp/servers")
@handle_errors()
@trace_function(attributes={"component": "list_mcp_servers"})
async def list_mcp_servers():
    """List MCP server configuration."""
    return {
        "servers": {
            "postgres": os.getenv("MCP_POSTGRES_URL", "http://127.0.0.1:8001/mcp"),
            "blob": os.getenv("MCP_BLOB_URL", "http://127.0.0.1:8002/mcp"),
            "email": os.getenv("MCP_EMAIL_URL", "http://127.0.0.1:8003/mcp"),
            "rag": os.getenv("MCP_RAG_URL", "http://127.0.0.1:8004/mcp"),
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
