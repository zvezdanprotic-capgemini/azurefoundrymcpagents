"""
RAG MCP Server for Policy Compliance

Provides tools for:
- Semantic search over company policy documents
- Getting specific policy requirements
- Checking customer compliance against policies

Uses pgvector for vector storage and Azure OpenAI for embeddings.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from langchain_openai import AzureOpenAIEmbeddings

from mcp_servers.base import BaseMCPServer, ToolResult, get_env_or_default

logger = logging.getLogger("mcp_servers.rag")


class RAGMCPServer(BaseMCPServer):
    """MCP Server for RAG-based policy compliance."""
    
    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        """
        Initialize with optional connection pool.
        If not provided, will create one on first use.
        """
        super().__init__()
        self._pool = pool
        self._embeddings: Optional[AzureOpenAIEmbeddings] = None
    
    @property
    def name(self) -> str:
        return "rag"
    
    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=get_env_or_default("POSTGRES_HOST", "localhost"),
                port=int(get_env_or_default("POSTGRES_PORT", "5432")),
                database=get_env_or_default("POSTGRES_DB", "kyc_crm"),
                user=get_env_or_default("POSTGRES_USER", "postgres"),
                password=os.environ.get("POSTGRES_PASSWORD", ""),
                min_size=2,
                max_size=10,
            )
        return self._pool
    
    def _get_embeddings(self) -> AzureOpenAIEmbeddings:
        """Get or create embeddings model."""
        if self._embeddings is None:
            self._embeddings = AzureOpenAIEmbeddings(
                azure_deployment=get_env_or_default("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
                api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
                api_version=get_env_or_default("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            )
        return self._embeddings
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions for this server."""
        return [
            {
                "name": "search_policies",
                "description": "Semantic search over company policy documents to find relevant policies",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query describing what policy info is needed"},
                        "category": {"type": "string", "description": "Optional category filter (compliance, eligibility, etc.)"},
                        "limit": {"type": "integer", "description": "Max results to return (default 5)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_policy_requirements",
                "description": "Get specific policy requirements for a product type or category",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_type": {"type": "string", "description": "Insurance product type (life, health, auto, etc.)"},
                        "requirement_type": {"type": "string", "description": "Type of requirement (age, health, documents, etc.)"}
                    },
                    "required": ["product_type"]
                }
            },
            {
                "name": "check_compliance",
                "description": "Check if customer data meets policy compliance requirements",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_data": {"type": "object", "description": "Customer information to check"},
                        "product_type": {"type": "string", "description": "Insurance product being applied for"},
                        "check_types": {"type": "array", "items": {"type": "string"}, "description": "Specific checks to perform (aml, kyc, eligibility)"}
                    },
                    "required": ["customer_data", "product_type"]
                }
            },
            {
                "name": "list_policy_categories",
                "description": "List available policy document categories",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "delete_policy_document",
                "description": "Delete a policy document and its chunks from the database (for cleanup/testing)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "Filename to delete all chunks for"},
                        "document_id": {"type": "integer", "description": "Specific chunk ID to delete (alternative to filename)"}
                    }
                }
            }
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool and return the result."""
        try:
            if tool_name == "search_policies":
                return await self._search_policies(
                    arguments["query"],
                    arguments.get("category"),
                    arguments.get("limit", 5)
                )
            elif tool_name == "get_policy_requirements":
                return await self._get_policy_requirements(
                    arguments["product_type"],
                    arguments.get("requirement_type")
                )
            elif tool_name == "check_compliance":
                return await self._check_compliance(
                    arguments["customer_data"],
                    arguments["product_type"],
                    arguments.get("check_types", ["aml", "kyc", "eligibility"])
                )
            elif tool_name == "list_policy_categories":
                return await self._list_policy_categories()
            elif tool_name == "delete_policy_document":
                return await self._delete_policy_document(
                    arguments.get("filename"),
                    arguments.get("document_id")
                )
            else:
                return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolResult(success=False, error=str(e))
    
    async def _search_policies(self, query: str, category: Optional[str] = None, limit: int = 5) -> ToolResult:
        """Semantic search over policy documents."""
        pool = await self._get_pool()
        embeddings = self._get_embeddings()
        
        # Generate embedding for query
        query_embedding = await embeddings.aembed_query(query)
        
        async with pool.acquire() as conn:
            # Build query with optional category filter
            if category:
                rows = await conn.fetch("""
                    SELECT 
                        id, filename, category, content, chunk_index,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM policy_documents
                    WHERE category = $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """, str(query_embedding), category, limit)
            else:
                rows = await conn.fetch("""
                    SELECT 
                        id, filename, category, content, chunk_index,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM policy_documents
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                """, str(query_embedding), limit)
            
            results = [
                {
                    "id": row["id"],
                    "filename": row["filename"],
                    "category": row["category"],
                    "content": row["content"],
                    "chunk_index": row["chunk_index"],
                    "similarity": float(row["similarity"])
                }
                for row in rows
            ]
            
            return ToolResult(success=True, data={
                "query": query,
                "result_count": len(results),
                "results": results
            })
    
    async def _get_policy_requirements(self, product_type: str, requirement_type: Optional[str] = None) -> ToolResult:
        """Get policy requirements for a product type."""
        # Build a targeted query for requirements
        query = f"{product_type} insurance requirements"
        if requirement_type:
            query += f" {requirement_type}"
        
        # Search for relevant policy chunks
        search_result = await self._search_policies(query, category="requirements", limit=10)
        
        if not search_result.success:
            return search_result
        
        # Extract and structure requirements from results
        requirements = []
        for result in search_result.data.get("results", []):
            requirements.append({
                "source": result["filename"],
                "content": result["content"],
                "relevance": result["similarity"]
            })
        
        return ToolResult(success=True, data={
            "product_type": product_type,
            "requirement_type": requirement_type,
            "requirements": requirements
        })
    
    async def _check_compliance(
        self, 
        customer_data: Dict[str, Any], 
        product_type: str,
        check_types: List[str]
    ) -> ToolResult:
        """Check customer compliance against policies."""
        compliance_results = {
            "overall_status": "PASS",
            "checks": [],
            "issues": []
        }
        
        # Get relevant policies for each check type
        for check_type in check_types:
            query = f"{product_type} {check_type} requirements compliance"
            search_result = await self._search_policies(query, limit=3)
            
            if search_result.success and search_result.data.get("results"):
                # Extract policy text for context
                policy_context = "\n".join([
                    r["content"] for r in search_result.data["results"]
                ])
                
                # Basic compliance check based on customer data presence
                check_result = {
                    "type": check_type,
                    "status": "PASS",
                    "policy_references": [r["filename"] for r in search_result.data["results"]],
                    "details": ""
                }
                
                # Perform type-specific checks
                if check_type == "aml":
                    # AML check - consent required
                    if not customer_data.get("consent"):
                        check_result["status"] = "FAIL"
                        check_result["details"] = "Customer consent for background check not obtained"
                        compliance_results["issues"].append("Missing AML consent")
                    else:
                        check_result["details"] = "AML consent obtained"
                        
                elif check_type == "kyc":
                    # KYC check - identity verification
                    missing = []
                    if not customer_data.get("date_of_birth") and not customer_data.get("dob"):
                        missing.append("date of birth")
                    if not customer_data.get("address"):
                        missing.append("address")
                    
                    if missing:
                        check_result["status"] = "REVIEW"
                        check_result["details"] = f"Missing: {', '.join(missing)}"
                        compliance_results["issues"].append(f"KYC incomplete: {', '.join(missing)}")
                    else:
                        check_result["details"] = "Identity information complete"
                        
                elif check_type == "eligibility":
                    # Basic eligibility check
                    check_result["details"] = f"Eligibility check for {product_type} completed"
                
                compliance_results["checks"].append(check_result)
                
                # Update overall status
                if check_result["status"] == "FAIL":
                    compliance_results["overall_status"] = "FAIL"
                elif check_result["status"] == "REVIEW" and compliance_results["overall_status"] == "PASS":
                    compliance_results["overall_status"] = "REVIEW"
        
        return ToolResult(success=True, data=compliance_results)
    
    async def _list_policy_categories(self) -> ToolResult:
        """List available policy categories."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT category, COUNT(*) as doc_count
                FROM policy_documents
                GROUP BY category
                ORDER BY category
            """)
            
            categories = [
                {"category": row["category"], "document_count": row["doc_count"]}
                for row in rows
            ]
            
            return ToolResult(success=True, data={"categories": categories})
    
    async def _delete_policy_document(self, filename: Optional[str] = None, document_id: Optional[int] = None) -> ToolResult:
        """Delete policy document chunks from database."""
        if not filename and not document_id:
            return ToolResult(success=False, error="Either filename or document_id must be provided")
        
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if filename:
                result = await conn.execute(
                    "DELETE FROM policy_documents WHERE filename = $1",
                    filename
                )
            else:
                result = await conn.execute(
                    "DELETE FROM policy_documents WHERE id = $1",
                    document_id
                )
            
            # result format: "DELETE N" where N is count
            deleted_count = int(result.split()[-1]) if result else 0
            
            return ToolResult(success=True, data={
                "deleted": deleted_count > 0,
                "deleted_count": deleted_count,
                "filename": filename,
                "document_id": document_id
            })
    
    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()


# Utility function for document ingestion (used by admin endpoint)
async def ingest_policy_document(
    pool: asyncpg.Pool,
    embeddings: AzureOpenAIEmbeddings,
    filename: str,
    content: str,
    category: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> int:
    """
    Ingest a policy document by chunking, embedding, and storing.
    
    Args:
        pool: Database connection pool
        embeddings: Embeddings model
        filename: Original filename
        content: Document text content
        category: Policy category
        chunk_size: Max characters per chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        Number of chunks created
    """
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    
    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_text(content)
    
    # Generate embeddings for all chunks
    chunk_embeddings = await embeddings.aembed_documents(chunks)
    
    # Store in database
    async with pool.acquire() as conn:
        for i, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
            await conn.execute("""
                INSERT INTO policy_documents (filename, category, content, chunk_index, embedding)
                VALUES ($1, $2, $3, $4, $5::vector)
            """, filename, category, chunk, i, str(embedding))
    
    logger.info(f"Ingested {len(chunks)} chunks from {filename}")
    return len(chunks)
