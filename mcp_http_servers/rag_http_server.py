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
        "status": "ok",
        "port": 8004
    })


async def get_pool() -> asyncpg.Pool:
    """
    Get or create PostgreSQL connection pool for policy document database.
    
    Uses lazy initialization pattern - creates pool on first call and reuses it.
    Pool maintains 2-10 connections for efficient database access with pgvector.
    
    Returns:
        asyncpg.Pool: Connection pool for policy_documents table
    """
    global _pool
    if _pool is None:
        # Create connection pool with configuration from environment variables
        _pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "kyc_crm"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            min_size=2,    # Minimum 2 connections always open
            max_size=10,   # Maximum 10 concurrent connections
        )
    return _pool


def get_embeddings() -> AzureOpenAIEmbeddings:
    """
    Get or create Azure OpenAI embeddings model for semantic search.
    
    Uses lazy initialization pattern - creates model on first call and reuses it.
    The embeddings model converts text to vectors for similarity search with pgvector.
    
    Returns:
        AzureOpenAIEmbeddings: Configured text-embedding-ada-002 model
    """
    global _embeddings
    if _embeddings is None:
        # Initialize Azure OpenAI embeddings with configuration from environment
        _embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
    return _embeddings


@mcp.tool()
async def search_policies(query: str, category: Optional[str] = None, limit: int = 5) -> dict:
    """
    Semantic search over company policy documents to find relevant policies.
    
    This tool:
    1. Converts the natural language query to a vector embedding
    2. Uses pgvector's cosine similarity (<=> operator) to find similar document chunks
    3. Optionally filters by category (compliance, aml, kyc, eligibility, etc.)
    4. Returns top N most similar policy chunks with similarity scores
    
    Args:
        query: Natural language search query (e.g., "home insurance age requirements")
        category: Optional filter by document category (e.g., "compliance", "eligibility")
        limit: Maximum number of results to return (default: 5)
        
    Returns:
        Dict with query info, result count, and list of matching policy chunks with similarity scores
    """
    pool = await get_pool()
    embeddings = get_embeddings()
    
    # Generate embedding vector for the query text using Azure OpenAI
    query_embedding = await embeddings.aembed_query(query)
    
    async with pool.acquire() as conn:
        # Build query with optional category filter
        if category:
            # Search within specific category only
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
            # Search across all categories
            rows = await conn.fetch("""
                SELECT 
                    id, filename, category, content, chunk_index,
                    1 - (embedding <=> $1::vector) as similarity
                FROM policy_documents
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, str(query_embedding), limit)
        
        # Convert database rows to result dictionaries
        results = [
            {
                "id": row["id"],
                "filename": row["filename"],
                "category": row["category"],
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "similarity": float(row["similarity"])  # 0.0 to 1.0, higher is more similar
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
    """
    Get specific policy requirements for a product type or category.
    
    This tool:
    1. Builds a semantic search query combining product type and optional requirement type
    2. Searches policy documents in compliance/eligibility/requirements categories
    3. Returns top 3 most relevant policy requirement chunks
    
    Use cases:
    - Get all requirements for a product: product_type="home_insurance"
    - Get specific requirements: product_type="home_insurance", requirement_type="age_restrictions"
    - Get eligibility criteria: product_type="auto_insurance", requirement_type="eligibility"
    
    Args:
        product_type: Product or policy type (e.g., 'home_insurance', 'life_insurance', 'auto_insurance')
        requirement_type: Optional specific requirement category (e.g., 'age_restrictions', 'eligibility', 'compliance')
        
    Returns:
        Dict with product info and list of relevant requirement chunks with similarity scores
    """
    pool = await get_pool()
    
    # Build semantic search query combining product and requirement types
    search_query = f"{product_type} policy requirements"
    if requirement_type:
        search_query += f" {requirement_type}"
    
    # Convert query to embedding vector
    embeddings = get_embeddings()
    query_embedding = await embeddings.aembed_query(search_query)
    
    async with pool.acquire() as conn:
        # Search only in policy requirement categories
        rows = await conn.fetch("""
            SELECT filename, category, content, chunk_index,
                   1 - (embedding <=> $1::vector) as similarity
            FROM policy_documents
            WHERE category IN ('compliance', 'eligibility', 'requirements')
            ORDER BY embedding <=> $1::vector
            LIMIT 3
        """, str(query_embedding))
        
        # Format results with source and similarity information
        requirements = [
            {
                "source": row["filename"],
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "similarity": float(row["similarity"])  # Higher score = more relevant
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
    """
    Check if customer data meets policy compliance requirements.
    
    This tool:
    1. Builds a customer profile summary including age, location, and product type
    2. Searches for relevant compliance, AML, KYC, and eligibility policies
    3. Returns matching policy chunks that apply to the customer situation
    4. Performs a simple compliance check (production systems should use LLM interpretation)
    
    Check types:
    - aml: Anti-Money Laundering checks
    - kyc: Know Your Customer verification
    - eligibility: Product eligibility criteria
    
    Args:
        customer_data: Dict with customer info (e.g., {"age": 35, "location": "California", "income": 75000})
        product_type: Product customer is applying for (e.g., "home_insurance", "auto_insurance")
        check_types: List of compliance check types to perform (default: ["aml", "kyc", "eligibility"])
        
    Returns:
        Dict with compliance status, checks performed, any issues found, and relevant policy excerpts
    """
    pool = await get_pool()
    embeddings = get_embeddings()
    
    # Build a natural language summary of the customer and their application
    customer_summary = f"Customer applying for {product_type}: "
    if "age" in customer_data:
        customer_summary += f"age {customer_data['age']}, "
    if "location" in customer_data:
        customer_summary += f"location {customer_data['location']}, "
    customer_summary += f"checks needed: {', '.join(check_types)}"
    
    # Convert customer summary to embedding for semantic search
    query_embedding = await embeddings.aembed_query(customer_summary)
    
    async with pool.acquire() as conn:
        # Find policies relevant to this customer's compliance check
        rows = await conn.fetch("""
            SELECT filename, category, content,
                   1 - (embedding <=> $1::vector) as similarity
            FROM policy_documents
            WHERE category IN ('compliance', 'aml', 'kyc', 'eligibility')
            ORDER BY embedding <=> $1::vector
            LIMIT 5
        """, str(query_embedding))
        
        # Format relevant policy excerpts
        relevant_policies = [
            {
                "source": row["filename"],
                "category": row["category"],
                "content": row["content"],
                "similarity": float(row["similarity"])  # How relevant this policy is to the customer
            }
            for row in rows
        ]
    
    # Simple compliance check logic
    # Note: Production systems should use an LLM to interpret policy text and make decisions
    compliance_status = {
        "compliant": True,  # Default to compliant (LLM would provide real assessment)
        "checks_performed": check_types,
        "issues": [],  # LLM would populate with specific compliance issues
        "relevant_policies": relevant_policies  # Policies that apply to this customer
    }
    
    return compliance_status


@mcp.tool()
async def list_policy_categories() -> dict:
    """
    List available policy document categories in the database.
    
    This tool:
    1. Queries the database to get all unique policy categories
    2. Counts how many document chunks exist in each category
    3. Returns a summary of available policy categories
    
    Use this to:
    - Discover what policy types are available for search
    - Understand the policy document inventory
    - Check coverage of different policy areas
    
    Common categories:
    - compliance: General compliance policies
    - aml: Anti-Money Laundering policies
    - kyc: Know Your Customer policies  
    - eligibility: Product eligibility criteria
    - requirements: Product requirement specifications
    - underwriting: Underwriting rules and guidelines
    
    Returns:
        Dict with total category count and list of categories with document counts
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Group by category and count document chunks in each
        rows = await conn.fetch("""
            SELECT category, COUNT(*) as document_count
            FROM policy_documents
            GROUP BY category
            ORDER BY category
        """)
        
        # Format category information
        categories = [
            {
                "category": row["category"],
                "document_count": row["document_count"]  # Number of chunks in this category
            }
            for row in rows
        ]
    
    return {
        "total_categories": len(categories),
        "categories": categories
    }


@mcp.tool()
async def delete_policy_document(filename: Optional[str] = None, document_id: Optional[int] = None) -> dict:
    """
    Delete a policy document and its chunks from the database.
    
    This tool:
    1. Accepts either a filename or document ID to identify the document(s) to delete
    2. Removes all matching rows from the policy_documents table
    3. Returns the number of chunks deleted
    
    Use cases:
    - Cleanup: Remove outdated policy documents
    - Testing: Clear test data between test runs
    - Updates: Delete old versions before uploading new policy versions
    
    Note: This deletes ALL chunks associated with the filename (if provided)
    or the specific chunk by ID (if document_id provided).
    
    Args:
        filename: Optional filename to delete (removes ALL chunks from this file)
        document_id: Optional specific document chunk ID to delete
        
    Returns:
        Dict with deletion status and count of deleted chunks
        
    Raises:
        ValueError: If neither filename nor document_id is provided
    """
    pool = await get_pool()
    
    # Validate that at least one identifier was provided
    if not filename and not document_id:
        raise ValueError("Either filename or document_id must be provided")
    
    async with pool.acquire() as conn:
        if filename:
            # Delete all chunks from this file
            result = await conn.execute(
                "DELETE FROM policy_documents WHERE filename = $1",
                filename
            )
        else:
            # Delete specific chunk by ID
            result = await conn.execute(
                "DELETE FROM policy_documents WHERE id = $1",
                document_id
            )
        
        # Extract number of deleted rows from result string (e.g., "DELETE 3")
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
