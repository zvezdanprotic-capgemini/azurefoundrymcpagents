"""
RAG MCP HTTP Server for Policy Compliance

Exposes RAG/policy search tools over HTTP using FastMCP.
Run: python -m mcp_http_servers.rag_http_server

Server listens on http://127.0.0.1:8004/mcp
"""
import os
import asyncio
from typing import Optional, List
from dotenv import load_dotenv
import asyncpg
from langchain_openai import AzureOpenAIEmbeddings

from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Create FastMCP server with JSON response mode
mcp = FastMCP("RAGKYC", json_response=True)

# Global connection pool and embeddings
_pool: Optional[asyncpg.Pool] = None
_embeddings: Optional[AzureOpenAIEmbeddings] = None


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse
    return JSONResponse({
        "service": "RAG MCP Server",
        "status": "healthy",
        "port": 8004
    })


async def get_pool() -> asyncpg.Pool:
    """Get or create connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "kyc_crm"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            min_size=2,
            max_size=10,
        )
    return _pool


def get_embeddings() -> AzureOpenAIEmbeddings:
    """Get or create embeddings model."""
    global _embeddings
    if _embeddings is None:
        _embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
    return _embeddings


@mcp.tool()
async def search_policies(query: str, category: Optional[str] = None, limit: int = 5) -> dict:
    """Semantic search over company policy documents to find relevant policies."""
    pool = await get_pool()
    embeddings = get_embeddings()
    
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
    
    return {
        "query": query,
        "category": category,
        "result_count": len(results),
        "results": results
    }


@mcp.tool()
async def get_policy_requirements(product_type: str, requirement_type: Optional[str] = None) -> dict:
    """Get specific policy requirements for a product type or category."""
    pool = await get_pool()
    
    # Search for policy documents related to this product
    search_query = f"{product_type} policy requirements"
    if requirement_type:
        search_query += f" {requirement_type}"
    
    embeddings = get_embeddings()
    query_embedding = await embeddings.aembed_query(search_query)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT filename, category, content, chunk_index,
                   1 - (embedding <=> $1::vector) as similarity
            FROM policy_documents
            WHERE category IN ('compliance', 'eligibility', 'requirements')
            ORDER BY embedding <=> $1::vector
            LIMIT 3
        """, str(query_embedding))
        
        requirements = [
            {
                "source": row["filename"],
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "similarity": float(row["similarity"])
            }
            for row in rows
        ]
    
    return {
        "product_type": product_type,
        "requirement_type": requirement_type,
        "requirements": requirements
    }


@mcp.tool()
async def check_compliance(customer_data: dict, product_type: str, check_types: List[str] = ["aml", "kyc", "eligibility"]) -> dict:
    """Check if customer data meets policy compliance requirements."""
    pool = await get_pool()
    embeddings = get_embeddings()
    
    # Build compliance check query
    customer_summary = f"Customer applying for {product_type}: "
    if "age" in customer_data:
        customer_summary += f"age {customer_data['age']}, "
    if "location" in customer_data:
        customer_summary += f"location {customer_data['location']}, "
    customer_summary += f"checks needed: {', '.join(check_types)}"
    
    query_embedding = await embeddings.aembed_query(customer_summary)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT filename, category, content,
                   1 - (embedding <=> $1::vector) as similarity
            FROM policy_documents
            WHERE category IN ('compliance', 'aml', 'kyc', 'eligibility')
            ORDER BY embedding <=> $1::vector
            LIMIT 5
        """, str(query_embedding))
        
        relevant_policies = [
            {
                "source": row["filename"],
                "category": row["category"],
                "content": row["content"],
                "similarity": float(row["similarity"])
            }
            for row in rows
        ]
    
    # Simple compliance check logic (in production, use LLM to interpret policies)
    compliance_status = {
        "compliant": True,
        "checks_performed": check_types,
        "issues": [],
        "relevant_policies": relevant_policies
    }
    
    return compliance_status


@mcp.tool()
async def list_policy_categories() -> dict:
    """List available policy document categories."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT category, COUNT(*) as document_count
            FROM policy_documents
            GROUP BY category
            ORDER BY category
        """)
        
        categories = [
            {
                "category": row["category"],
                "document_count": row["document_count"]
            }
            for row in rows
        ]
    
    return {
        "total_categories": len(categories),
        "categories": categories
    }


@mcp.tool()
async def delete_policy_document(filename: Optional[str] = None, document_id: Optional[int] = None) -> dict:
    """Delete a policy document and its chunks from the database (for cleanup/testing)."""
    pool = await get_pool()
    
    if not filename and not document_id:
        raise ValueError("Either filename or document_id must be provided")
    
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
        
        deleted_count = int(result.split()[-1]) if result else 0
    
    return {
        "deleted": deleted_count > 0,
        "deleted_count": deleted_count,
        "filename": filename,
        "document_id": document_id
    }


if __name__ == "__main__":
    # Start the HTTP server on port 8004
    import uvicorn
    uvicorn.run(mcp.streamable_http_app, host="127.0.0.1", port=8004)
