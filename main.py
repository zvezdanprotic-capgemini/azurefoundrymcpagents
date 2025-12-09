
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

from graph import app_graph, initialize_mcp_servers
from langchain_core.messages import HumanMessage, AIMessage

# MCP Servers
from mcp_servers import PostgresMCPServer, BlobMCPServer, EmailMCPServer, RAGMCPServer

# Load environment variables
load_dotenv()

# Configure logging with explicit formatter/handler to ensure visibility under uvicorn
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

# MCP Servers (initialized at startup)
mcp_postgres: Optional[PostgresMCPServer] = None
mcp_blob: Optional[BlobMCPServer] = None
mcp_email: Optional[EmailMCPServer] = None
mcp_rag: Optional[RAGMCPServer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and cleanup MCP servers."""
    global mcp_postgres, mcp_blob, mcp_email, mcp_rag
    
    logger.info("Initializing MCP servers...")
    
    # Initialize MCP servers
    mcp_postgres = PostgresMCPServer()
    mcp_blob = BlobMCPServer()
    mcp_email = EmailMCPServer()
    mcp_rag = RAGMCPServer()
    
    # Register with graph
    initialize_mcp_servers({
        "postgres": mcp_postgres,
        "blob": mcp_blob,
        "email": mcp_email,
        "rag": mcp_rag,
    })
    
    logger.info("MCP servers initialized successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down MCP servers...")
    if mcp_postgres:
        await mcp_postgres.close()
    if mcp_rag:
        await mcp_rag.close()
    logger.info("MCP servers shut down")


app = FastAPI(
    title="Azure AI Agents KYC Orchestrator", 
    version="3.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session persistence
SESSIONS_FILE = Path("sessions.json")

def load_sessions():
    """Load sessions from disk."""
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE, 'r') as f:
                loaded = json.load(f)
                logger.info(f"Loaded {len(loaded)} sessions from disk")
                return loaded
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            return {}
    return {}

def save_sessions():
    """Save sessions to disk."""
    try:
        with open(SESSIONS_FILE, 'w') as f:
            json.dump(sessions, f, indent=2)
        logger.debug(f"Saved {len(sessions)} sessions to disk")
    except Exception as e:
        logger.error(f"Error saving sessions: {e}")

# In-memory session storage with disk persistence (use Redis/Azure Cache in production)
sessions = load_sessions()

# Azure OpenAI client for welcome messages
azure_client = AzureOpenAI(
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-21"
) if os.environ.get("AZURE_OPENAI_ENDPOINT") else None

class CustomerInput(BaseModel):
    name: str
    email: EmailStr
    insurance_needs: str
    documents: Dict[str, str] = {}

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None

class SessionUpdate(BaseModel):
    additional_data: Dict[str, Any] = {}

def build_user_friendly_message(decision: Dict[str, Any]) -> str:
    """Create a concise, user-friendly message from a formal agent decision JSON."""
    try:
        stage = decision.get("stage") or "verification"
        dec = decision.get("decision") or "PENDING"
        reason = decision.get("reason")
        risk = decision.get("risk_level")
        next_action = decision.get("next_action")
        checks = decision.get("checks") or []

        # Build summary lines
        header = f"Status: {dec}."
        parts = []
        if reason:
            parts.append(reason)
        # Collect failed checks succinctly
        failed = [c for c in checks if c.get("status") == "FAIL"]
        if failed:
            names = ", ".join(c.get("name", "item").replace("_", " ") for c in failed[:4])
            parts.append(f"Items needing attention: {names}.")
        if next_action:
            parts.append(f"Next step: {next_action.replace('_', ' ')}.")
        if risk:
            parts.append(f"Risk level: {risk}.")

        # Tailor by stage
        stage_prefix = {
            "verification": "Verification update",
            "eligibility": "Eligibility update",
            "compliance": "Compliance update",
            "recommendation": "Recommendation update",
            "action": "Finalization update",
        }.get(stage, "Case update")

        return f"{stage_prefix}: {header} " + " ".join(parts)
    except Exception:
        return "Update: We need a bit more information to proceed."

class DocumentUploadForm(BaseModel):
    document_type: Optional[str] = "other"
    filename: Optional[str] = None

async def call_azure_ai(prompt: str, context: Dict[str, Any] = None) -> str:
    """Call Azure OpenAI for intelligent responses."""
    if not azure_client:
        logger.warning("Azure OpenAI client not configured, using fallback response")
        return "I understand your request. Let me help you with the next step in your insurance application."
    
    try:
        messages = [
            {"role": "system", "content": "You are a helpful insurance KYC assistant. Be professional, concise, and guide users through the process."},
            {"role": "user", "content": prompt}
        ]
        
        if context:
            context_str = f"Customer context: {context}"
            messages.insert(1, {"role": "system", "content": context_str})
        
        response = azure_client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Azure OpenAI call failed: {str(e)}")
        return "I'm here to help you with your insurance application. Please let me know what information you need to provide."

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Azure AI Agents KYC Orchestrator is running", "status": "healthy", "version": "2.0.0 (Local Agents)"}

@app.post("/start-session")
async def start_session(customer: CustomerInput):
    """Start a new KYC session for a customer."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "customer": customer.dict(),
        "step": "intake",
        "status": "in_progress",
        "chat_history": [],
        "created_at": asyncio.get_event_loop().time(),
        "step_results": {},  # Stores array of conversations per step
        "user_type": "insurance_employee",
        "thread_ids": {}  # Kept for compatibility
    }
    
    # Generate welcome message using Azure AI
    welcome_message = await call_azure_ai(
        f"Generate a professional welcome message for an insurance employee reviewing the KYC case for {customer.name}. The customer is interested in {customer.insurance_needs}. This message should be from the system to the insurance employee, not to the customer.",
        {"customer_name": customer.name, "insurance_needs": customer.insurance_needs, "user_type": "insurance_employee"}
    )
    
    sessions[session_id]["chat_history"].append({
        "role": "assistant",
        "content": welcome_message,
        "timestamp": str(asyncio.get_event_loop().time())
    })
    
    save_sessions()  # Persist new session
    
    logger.info(f"Started session {session_id} for customer {customer.name}")
    return {
        "session_id": session_id, 
        "next_step": "intake",
        "welcome_message": welcome_message,
        "status": "started",
        "agent_step": "intake",
        "agent_label": "Customer Intake"
    }



@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session details and current status."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "customer": session["customer"],
        "current_step": session["step"],
        "status": session["status"],
        "chat_history": session["chat_history"],
        "step_results": session.get("step_results", {}),
        "thread_ids": session.get("thread_ids", {}),
        "agent_step": session["step"],
        "agent_label": session["step"].capitalize()
    }

@app.post("/chat/{session_id}")
async def chat_with_agent(session_id: str, message: ChatMessage):
    """Unified chat endpoint: records user message, invokes LangGraph workflow."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    current_step = session["step"]

    # Record user message
    user_msg = {
        "role": "user",
        "content": message.content,
        "timestamp": str(asyncio.get_event_loop().time())
    }
    session["chat_history"].append(user_msg)
    
    # Extract and accumulate customer data from messages (Preserved logic)
    content_lower = message.content.lower()
    import re
    
    # Extract DOB patterns
    dob_patterns = [
        r'(\d{2}[./]\d{2}[./]\d{4})',
        r'(\d{4}[-]\d{2}[-]\d{2})',
    ]
    for pattern in dob_patterns:
        match = re.search(pattern, message.content)
        if match:
            session["customer"]["date_of_birth"] = match.group(1)
            logger.info(f"[/chat] Extracted DOB: {match.group(1)}")
            break
    
    # Extract address
    address_indicators = ['address:', 'address is', 'lives at', 'residing at']
    for indicator in address_indicators:
        if indicator in content_lower:
            idx = content_lower.find(indicator) + len(indicator)
            remaining = message.content[idx:].strip()
            end_markers = [' and ', '\n', '.', ', consent', ', documents']
            address_end = len(remaining)
            for marker in end_markers:
                pos = remaining.find(marker)
                if pos > 10:
                    address_end = min(address_end, pos)
            
            address = remaining[:address_end].strip()
            if len(address) > 5:
                session["customer"]["address"] = address
                logger.info(f"[/chat] Extracted address: {address}")
                break
    
    # Extract consent
    consent_keywords = ['consent: yes', 'consent confirmed', 'provided consent', 'consents to', 'agreed to']
    if any(kw in content_lower for kw in consent_keywords):
        if 'consent' not in session["customer"]:
            session["customer"]["consent"] = "confirmed"
            logger.info(f"[/chat] Extracted consent: confirmed")
    
    # Extract documents
    doc_keywords = ['license', 'passport', 'documents:', 'id card']
    if any(kw in content_lower for kw in doc_keywords):
        if 'documents_mentioned' not in session["customer"]:
            session["customer"]["documents_mentioned"] = message.content
            logger.info(f"[/chat] Noted documents mentioned in message")

    # Prepare State for LangGraph
    lc_messages = []
    for msg in session["chat_history"]:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))
            
    initial_state = {
        "messages": lc_messages,
        "customer_data": session["customer"],
        "next_step": current_step,
        "step_results": session.get("step_results", {}),
        "session_id": session_id,
        "thread_ids": session.get("thread_ids", {}),
        "final_response": ""
    }
    
    logger.info(f"[/chat] Invoking LangGraph for session {session_id} at step {current_step}")
    
    # Invoke the Graph
    final_state = await app_graph.ainvoke(initial_state)
    
    # Update Session with results from Graph
    session["customer"] = final_state["customer_data"]
    session["step_results"] = final_state["step_results"]
    session["thread_ids"] = final_state["thread_ids"]
    
    # Determine if we advanced
    previous_step = current_step
    new_step = final_state["next_step"]
    
    # Handle "FINISH" or advancement
    if new_step == "FINISH":
        session["status"] = "complete"
        session["step"] = "action" # Stay on last step or move to a completed state
        logger.info(f"[/chat] Workflow completed for session {session_id}")
    elif new_step != previous_step:
        session["step"] = new_step
        logger.info(f"[/chat] Advanced from {previous_step} to {new_step}")
    
    # Get the latest response from the graph execution
    # The graph returns the final state. The last message should be the agent's response.
    last_message = final_state["messages"][-1]
    response_content = last_message.content if isinstance(last_message, AIMessage) else "Processing complete."

    # Extract decision structure from step results
    decision_struct = None
    user_friendly_message = None
    current_step = session["step"]
    step_results = final_state.get("step_results", {})
    
    if current_step in step_results and step_results[current_step]:
        latest_result = step_results[current_step][-1]
        parsed_decision = latest_result.get("parsed_decision", {})
        if isinstance(parsed_decision, dict):
            decision_struct = parsed_decision
            # Prefer agent's user_message if available
            user_friendly_message = parsed_decision.get("user_message")
            # Fallback to building one if not provided
            if not user_friendly_message:
                user_friendly_message = build_user_friendly_message(parsed_decision)
    
    # Record assistant message (prefer friendly text when available)
    assistant_msg = {
        "role": "assistant",
        "content": user_friendly_message or response_content,
        "timestamp": str(asyncio.get_event_loop().time()),
        "agent_step": session["step"]
    }
    session["chat_history"].append(assistant_msg)
    save_sessions()

    return {
        "response": response_content,
        "session_status": session["status"],
        "current_step": session["step"],
        "agent_step": session["step"],
        "agent_label": session["step"].capitalize(),
        "advanced": new_step != previous_step,
        "advancement": {"from": previous_step, "to": new_step} if new_step != previous_step else None,
        # Echo formal decision if available, alongside a user-friendly text for the UI
        "decision": decision_struct if isinstance(decision_struct, dict) else None,
        "user_message": user_friendly_message,
    }

@app.put("/session/{session_id}")
async def update_session(session_id: str, update: SessionUpdate):
    """Update session with additional data or documents."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update customer data
    if update.additional_data:
        session["customer"].update(update.additional_data)
    
    save_sessions()  # Persist updates
    
    logger.info(f"Updated session {session_id} with additional data")
    return {"status": "updated", "session_id": session_id}


@app.get("/session/{session_id}/panel-data")
async def get_session_panel_data(session_id: str, document_type: Optional[str] = None):
    """Aggregate session info, CRM customer, previous sessions, and user documents."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not mcp_postgres or not mcp_blob:
        raise HTTPException(status_code=503, detail="MCP servers not initialized")

    email = session["customer"].get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Session missing customer email")

    # Lookup customer in CRM
    customer_lookup = await mcp_postgres.call_tool("get_customer_by_email", {"email": email})
    if not customer_lookup.success:
        raise HTTPException(status_code=500, detail=customer_lookup.error)
    customer_data = customer_lookup.data

    account_id = customer_data.get("account", {}).get("id") if customer_data.get("found") else None
    contact_id = customer_data.get("contact", {}).get("id") if customer_data.get("found") else None

    # Previous KYC sessions
    previous = {"sessions": []}
    if contact_id:
        prev_sessions = await mcp_postgres.call_tool("get_previous_kyc_sessions", {"contact_id": contact_id})
        previous = prev_sessions.data if prev_sessions.success else {"error": prev_sessions.error}

    # Customer documents from Blob Storage
    documents = {"documents": [], "document_count": 0}
    if account_id:
        docs = await mcp_blob.call_tool("list_customer_documents", {"account_id": str(account_id), "document_type": document_type})
        documents = docs.data if docs.success else {"error": docs.error}

    return {
        "session": {
            "session_id": session_id,
            "customer": session["customer"],
            "current_step": session["step"],
            "status": session["status"],
        },
        "crm": customer_data,
        "previous_sessions": previous,
        "documents": documents,
    }


@app.get("/session/{session_id}/documents")
async def list_session_documents(session_id: str, document_type: Optional[str] = None):
    """List documents for the session’s customer from Blob Storage."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not mcp_postgres or not mcp_blob:
        raise HTTPException(status_code=503, detail="MCP servers not initialized")

    email = session["customer"].get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Session missing customer email")

    customer_lookup = await mcp_postgres.call_tool("get_customer_by_email", {"email": email})
    if not customer_lookup.success:
        raise HTTPException(status_code=500, detail=customer_lookup.error)
    customer_data = customer_lookup.data
    account_id = customer_data.get("account", {}).get("id") if customer_data.get("found") else None
    if not account_id:
        return {"documents": [], "document_count": 0, "message": "No account linked"}

    docs = await mcp_blob.call_tool("list_customer_documents", {"account_id": str(account_id), "document_type": document_type})
    if not docs.success:
        raise HTTPException(status_code=500, detail=docs.error)
    return docs.data


@app.post("/session/{session_id}/documents/upload")
async def upload_session_document(session_id: str, file: UploadFile = File(...), document_type: Optional[str] = "other"):
    """Upload a document for the session’s customer to Blob Storage."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not mcp_postgres or not mcp_blob:
        raise HTTPException(status_code=503, detail="MCP servers not initialized")

    email = session["customer"].get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Session missing customer email")

    # Resolve account_id
    customer_lookup = await mcp_postgres.call_tool("get_customer_by_email", {"email": email})
    if not customer_lookup.success:
        raise HTTPException(status_code=500, detail=customer_lookup.error)
    customer_data = customer_lookup.data
    account_id = customer_data.get("account", {}).get("id") if customer_data.get("found") else None
    if not account_id:
        raise HTTPException(status_code=400, detail="Customer has no linked account for document storage")

    # Read file content and upload via Blob MCP
    import base64
    content = await file.read()
    filename = file.filename or "upload.bin"
    content_type = file.content_type or "application/octet-stream"

    args = {
        "account_id": str(account_id),
        "filename": filename,
        "content_base64": base64.b64encode(content).decode("utf-8"),
        "content_type": content_type,
        "document_type": document_type,
        "metadata": {"session_id": session_id}
    }
    result = await mcp_blob.call_tool("upload_document", args)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {"status": "uploaded", **result.data}

@app.get("/steps")
async def get_workflow_steps():
    """Get the KYC workflow steps."""
    return {
        "steps": [
            {"id": "intake", "name": "Customer Intake", "description": "Collect basic customer information"},
            {"id": "verification", "name": "Identity Verification", "description": "Verify customer identity and documents"},
            {"id": "eligibility", "name": "Eligibility Assessment", "description": "Assess customer eligibility for insurance products"},
            {"id": "recommendation", "name": "Product Recommendation", "description": "Recommend suitable insurance products"},
            {"id": "compliance", "name": "Compliance Check", "description": "Perform regulatory compliance verification"},
            {"id": "action", "name": "Final Action", "description": "Complete onboarding or schedule follow-up"}
        ]
    }

@app.delete("/session/{session_id}")
async def end_session(session_id: str):
    """End and cleanup a session."""
    if session_id in sessions:
        del sessions[session_id]
        logger.info(f"Ended session {session_id}")
        return {"status": "session_ended", "session_id": session_id}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


# =====================
# Policy Management (RAG)
# =====================

class PolicyUploadRequest(BaseModel):
    filename: str
    content: str
    category: str = "general"


@app.post("/policies/upload")
async def upload_policy_document(request: PolicyUploadRequest):
    """
    Upload a policy document for RAG indexing.
    
    The document will be chunked, embedded using Azure OpenAI, 
    and stored in pgvector for semantic search.
    """
    if not mcp_rag:
        raise HTTPException(status_code=503, detail="RAG server not initialized")
    
    try:
        from mcp_servers.rag_server import ingest_policy_document
        from langchain_openai import AzureOpenAIEmbeddings
        
        # Get the pool and embeddings from RAG server
        pool = await mcp_rag._get_pool()
        embeddings = mcp_rag._get_embeddings()
        
        # Ingest the document
        chunk_count = await ingest_policy_document(
            pool=pool,
            embeddings=embeddings,
            filename=request.filename,
            content=request.content,
            category=request.category
        )
        
        logger.info(f"Ingested policy document: {request.filename} ({chunk_count} chunks)")
        
        return {
            "status": "success",
            "filename": request.filename,
            "category": request.category,
            "chunks_created": chunk_count
        }
        
    except Exception as e:
        logger.error(f"Error uploading policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/policies/categories")
async def list_policy_categories():
    """List available policy document categories."""
    if not mcp_rag:
        raise HTTPException(status_code=503, detail="RAG server not initialized")
    
    result = await mcp_rag.call_tool("list_policy_categories", {})
    if result.success:
        return result.data
    else:
        raise HTTPException(status_code=500, detail=result.error)


@app.get("/policies/search")
async def search_policies(query: str, category: Optional[str] = None, limit: int = 5):
    """Search policy documents using semantic search."""
    if not mcp_rag:
        raise HTTPException(status_code=503, detail="RAG server not initialized")
    
    result = await mcp_rag.call_tool("search_policies", {
        "query": query,
        "category": category,
        "limit": limit
    })
    
    if result.success:
        return result.data
    else:
        raise HTTPException(status_code=500, detail=result.error)


@app.post("/policies/upload-file")
async def upload_policy_file(
    file: UploadFile = File(...),
    category: str = "general",
    chunk_size: int = 1000
):
    """
    Upload a PDF or Word document for RAG indexing.
    
    The document will be converted to Markdown using docling,
    chunked, embedded, and stored in pgvector.
    
    Args:
        file: PDF or Word document file
        category: Document category for filtering
        chunk_size: Maximum characters per chunk (default 1000)
    """
    if not mcp_rag:
        raise HTTPException(status_code=503, detail="RAG server not initialized")
    
    # Validate file type
    filename = file.filename or "unknown"
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    if ext not in ['pdf', 'docx', 'doc']:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: .{ext}. Supported: .pdf, .docx, .doc"
        )
    
    # Validate chunk size
    if chunk_size < 500 or chunk_size > 4000:
        raise HTTPException(
            status_code=400,
            detail="Chunk size must be between 500 and 4000 characters"
        )
    
    try:
        from mcp_servers.document_processor import process_document
        
        # Read file content
        file_bytes = await file.read()
        
        # Get pool and embeddings from RAG server
        pool = await mcp_rag._get_pool()
        embeddings = mcp_rag._get_embeddings()
        
        # Process the document
        chunk_count, status = await process_document(
            pool=pool,
            embeddings=embeddings,
            file_bytes=file_bytes,
            filename=filename,
            category=category,
            chunk_size=chunk_size
        )
        
        logger.info(f"Uploaded and processed {filename}: {chunk_count} chunks")
        
        return {
            "status": "success",
            "filename": filename,
            "category": category,
            "chunk_size": chunk_size,
            "chunks_created": chunk_count
        }
        
    except ValueError as e:
        logger.error(f"Validation error uploading {filename}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading document {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/policies/documents")
async def list_policy_documents():
    """List all RAG documents with their status and chunk counts."""
    if not mcp_rag:
        raise HTTPException(status_code=503, detail="RAG server not initialized")
    
    try:
        from mcp_servers.document_processor import get_document_list
        
        pool = await mcp_rag._get_pool()
        documents = await get_document_list(pool)
        
        return {"documents": documents}
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/policies/documents/by-filename/{filename:path}")
async def get_policy_document(filename: str):
    """Get details for a specific RAG document."""
    if not mcp_rag:
        raise HTTPException(status_code=503, detail="RAG server not initialized")
    
    try:
        from mcp_servers.document_processor import get_document_details
        
        pool = await mcp_rag._get_pool()
        document = await get_document_details(pool, filename)
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document not found: {filename}")
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/policies/documents/chunks")
async def get_policy_document_chunks(filename: str):
    """Get all chunks for a specific RAG document."""
    if not mcp_rag:
        raise HTTPException(status_code=503, detail="RAG server not initialized")
    
    try:
        from mcp_servers.document_processor import get_document_chunks
        
        logger.info(f"Fetching chunks for filename: '{filename}'")
        
        pool = await mcp_rag._get_pool()
        chunks = await get_document_chunks(pool, filename)
        
        if not chunks:
            raise HTTPException(status_code=404, detail=f"No chunks found for document: {filename}")
        
        return {
            "filename": filename,
            "chunk_count": len(chunks),
            "chunks": chunks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chunks for {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/policies/documents/{document_id}/chunks")
async def get_policy_document_chunks_by_id(document_id: int):
    """Get all chunks for a document by its ID (representative row id)."""
    if not mcp_rag:
        raise HTTPException(status_code=503, detail="RAG server not initialized")

    try:
        from mcp_servers.document_processor import get_document_chunks_by_id

        logger.info(f"Fetching chunks for document_id: {document_id}")

        pool = await mcp_rag._get_pool()
        chunks = await get_document_chunks_by_id(pool, document_id)

        if not chunks:
            raise HTTPException(status_code=404, detail=f"No chunks found for document_id: {document_id}")

        # Also fetch filename for response context
        async with (await mcp_rag._get_pool()).acquire() as conn:
            filename = await conn.fetchval("SELECT filename FROM policy_documents WHERE id = $1", document_id)

        return {
            "id": document_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "chunks": chunks,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chunks for document_id {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/policies/documents/by-filename/{filename:path}")
async def delete_policy_document(filename: str):
    """Delete a RAG document and all its chunks."""
    if not mcp_rag:
        raise HTTPException(status_code=503, detail="RAG server not initialized")
    
    try:
        from mcp_servers.document_processor import delete_document
        
        pool = await mcp_rag._get_pool()
        deleted_count = await delete_document(pool, filename)
        
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Document not found: {filename}")
        
        logger.info(f"Deleted document {filename}: {deleted_count} chunks removed")
        
        return {
            "status": "deleted",
            "filename": filename,
            "chunks_deleted": deleted_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Detailed health check including all services."""
    health_status = {
        "status": "healthy",
        "timestamp": asyncio.get_event_loop().time(),
        "version": "3.0.0 (Agentic MCP)",
        "services": {
            "api": "healthy",
            "azure_openai": "unknown",
            "local_agents": "healthy",
            "mcp_servers": {
                "postgres": "initialized" if mcp_postgres else "not_initialized",
                "blob": "initialized" if mcp_blob else "not_initialized",
                "email": "initialized" if mcp_email else "not_initialized",
                "rag": "initialized" if mcp_rag else "not_initialized",
            }
        },
        "active_sessions": len(sessions)
    }
    
    # Check Azure OpenAI connectivity
    if azure_client:
        try:
            test_response = await call_azure_ai("Health check", {})
            health_status["services"]["azure_openai"] = "healthy"
        except Exception as e:
            health_status["services"]["azure_openai"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["services"]["azure_openai"] = "not_configured"
        health_status["status"] = "degraded"
    
    # Check MCP servers
    mcp_initialized = all([mcp_postgres, mcp_blob, mcp_email, mcp_rag])
    if not mcp_initialized:
        health_status["status"] = "degraded"
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

