"""
Main FastAPI Application with HTTP MCP Client

This version uses HTTP MCP servers running as separate processes.
Each MCP server runs on its own port and agents connect via HTTP.

Before running this application:
1. Start all MCP servers: ./start_all_mcp_servers.sh
2. Verify servers are running on ports 8001-8004
3. Then start this FastAPI app: uvicorn main_http:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import httpx
import uuid
import asyncio
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import AzureOpenAI
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from graph import app_graph
from langchain_core.messages import HumanMessage, AIMessage

# Import HTTP MCP Client
from mcp_client import initialize_mcp_client, get_mcp_client

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.environ.get("APP_LOG_LEVEL", "INFO").upper()
root_logger = logging.getLogger()
if not root_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
root_logger.setLevel(LOG_LEVEL)

logger = logging.getLogger("kyc.orchestrator")
logger.debug("Logger initialized with level %s", LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and cleanup HTTP MCP client."""
    logger.info("Initializing HTTP MCP client...")
    
    # Initialize HTTP MCP client (connects to servers on ports 8001-8004)
    mcp_client = initialize_mcp_client(
        postgres_url=os.getenv("MCP_POSTGRES_URL", "http://127.0.0.1:8001/mcp"),
        blob_url=os.getenv("MCP_BLOB_URL", "http://127.0.0.1:8002/mcp"),
        email_url=os.getenv("MCP_EMAIL_URL", "http://127.0.0.1:8003/mcp"),
        rag_url=os.getenv("MCP_RAG_URL", "http://127.0.0.1:8004/mcp"),
    )
    
    # Initialize connection
    await mcp_client.initialize()
    
    logger.info("HTTP MCP client initialized successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down HTTP MCP client...")
    await mcp_client.close()
    logger.info("HTTP MCP client shut down")


app = FastAPI(
    title="Azure AI Agents KYC Orchestrator (HTTP MCP)", 
    version="4.0.0",
    description="KYC system with HTTP MCP servers for true service decoupling",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session persistence
SESSIONS_FILE = Path("sessions.json")


def load_sessions() -> Dict[str, Any]:
    """Load sessions from file."""
    if SESSIONS_FILE.exists():
        with open(SESSIONS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_sessions(sessions: Dict[str, Any]):
    """Save sessions to file."""
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=2, default=str)


sessions = load_sessions()


# Pydantic models
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
async def root():
    """Health check endpoint."""
    return {
        "service": "KYC Orchestrator with HTTP MCP",
        "version": "4.0.0",
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
async def health():
    """Detailed health check including MCP server connectivity."""
    mcp_client = get_mcp_client()
    
    health_status = {
        "status": "healthy",
        "mcp_client": "connected",
        "mcp_tools_loaded": len(await mcp_client.get_tools())
    }
    
    return health_status


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint for KYC workflow.
    
    Uses LangGraph orchestrator with HTTP MCP clients.
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    # Get or create session
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
    
    return ChatResponse(
        response=ai_response,
        session_id=session_id,
        status=session["status"],
        current_step=session["current_step"],
        customer=session["customer"]
    )


@app.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    return {"sessions": list(sessions.values())}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id in sessions:
        del sessions[session_id]
        save_sessions(sessions)
        return {"deleted": True, "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


@app.get("/mcp/tools")
async def list_mcp_tools():
    """List all available MCP tools from HTTP servers."""
    mcp_client = get_mcp_client()
    tools = await mcp_client.get_tools()
    
    return {
        "total_tools": len(tools),
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
            }
            for tool in tools
        ]
    }


@app.get("/mcp/servers")
async def list_mcp_servers():
    """List MCP server configuration."""
    mcp_client = get_mcp_client()
    
    return {
        "servers": mcp_client.server_config,
        "status": "All servers should be running on their respective ports"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
