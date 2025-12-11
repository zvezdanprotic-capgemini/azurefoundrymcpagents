"""
PostgreSQL MCP HTTP Server

Exposes PostgreSQL/CRM tools over HTTP using FastMCP.
Run: python -m mcp_http_servers.postgres_http_server

Server listens on http://127.0.0.1:8001/mcp
"""
import os
import json
import asyncio
from typing import Optional
from uuid import UUID
from dotenv import load_dotenv
import asyncpg

from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Create FastMCP server with JSON response mode
mcp = FastMCP("PostgresKYC", json_response=True)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse
    return JSONResponse({
        "service": "PostgreSQL MCP Server",
        "status": "healthy",
        "port": 8001
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


@mcp.tool()
async def get_customer_by_email(email: str) -> dict:
    """Look up a customer (contact + account) by their email address."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                c.id as contact_id,
                c.first_name,
                c.last_name,
                c.email,
                c.created_at as contact_created,
                a.id as account_id,
                a.name as account_name,
                a.industry,
                a.billing_address
            FROM contacts c
            LEFT JOIN accounts a ON c.account_id = a.id
            WHERE c.email = $1
        """, email)
        
        if not row:
            return {"found": False, "message": "No customer found with this email"}
        
        return {
            "found": True,
            "contact": {
                "id": row["contact_id"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "email": row["email"],
                "created_at": row["contact_created"].isoformat() if row["contact_created"] else None
            },
            "account": {
                "id": row["account_id"],
                "name": row["account_name"],
                "industry": row["industry"],
                "billing_address": row["billing_address"]
            } if row["account_id"] else None
        }


@mcp.tool()
async def get_customer_history(contact_id: int, account_id: Optional[int] = None) -> dict:
    """Get a customer's order, quote, and invoice history."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # If no account_id provided, get it from contact
        if not account_id:
            row = await conn.fetchrow("SELECT account_id FROM contacts WHERE id = $1", contact_id)
            if row:
                account_id = row["account_id"]
        
        if not account_id:
            return {"orders": [], "quotes": [], "invoices": [], "message": "No account linked"}
        
        # Get orders
        orders = await conn.fetch("""
            SELECT id, order_number, order_date, status, total_amount
            FROM orders WHERE account_id = $1
            ORDER BY order_date DESC LIMIT 10
        """, account_id)
        
        # Get quotes
        quotes = await conn.fetch("""
            SELECT q.id, q.quote_number, q.status, q.total_price, q.valid_until
            FROM quotes q
            JOIN opportunities o ON q.opportunity_id = o.id
            WHERE o.account_id = $1
            ORDER BY q.created_at DESC LIMIT 10
        """, account_id)
        
        # Get invoices
        invoices = await conn.fetch("""
            SELECT id, invoice_number, status, issue_date, due_date, total_amount
            FROM invoices WHERE account_id = $1
            ORDER BY issue_date DESC LIMIT 10
        """, account_id)
        
        return {
            "orders": [dict(r) for r in orders],
            "quotes": [dict(r) for r in quotes],
            "invoices": [dict(r) for r in invoices]
        }


@mcp.tool()
async def get_previous_kyc_sessions(contact_id: int) -> dict:
    """Get list of previous KYC sessions for a customer."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sessions = await conn.fetch("""
            SELECT id, status, current_step, created_at, updated_at
            FROM kyc_sessions
            WHERE contact_id = $1
            ORDER BY created_at DESC LIMIT 10
        """, contact_id)
        
        return {
            "sessions": [
                {
                    "id": str(r["id"]),
                    "status": r["status"],
                    "current_step": r["current_step"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                    "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None
                }
                for r in sessions
            ]
        }


@mcp.tool()
async def save_kyc_session_state(
    session_id: str,
    status: str,
    current_step: str,
    customer_data: dict,
    contact_id: Optional[int] = None,
    step_results: Optional[dict] = None,
    chat_history: Optional[list] = None
) -> dict:
    """Save current KYC session state to database for persistence."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO kyc_sessions (id, contact_id, status, current_step, customer_data, step_results, chat_history, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (id) DO UPDATE SET
                contact_id = COALESCE(EXCLUDED.contact_id, kyc_sessions.contact_id),
                status = EXCLUDED.status,
                current_step = EXCLUDED.current_step,
                customer_data = EXCLUDED.customer_data,
                step_results = EXCLUDED.step_results,
                chat_history = EXCLUDED.chat_history,
                updated_at = NOW()
        """,
            UUID(session_id),
            contact_id,
            status,
            current_step,
            json.dumps(customer_data),
            json.dumps(step_results or {}),
            json.dumps(chat_history or [])
        )
        
        return {"saved": True, "session_id": session_id}


@mcp.tool()
async def load_kyc_session_state(session_id: str) -> dict:
    """Load a saved KYC session state from database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, contact_id, status, current_step, customer_data, step_results, chat_history, created_at, updated_at
            FROM kyc_sessions WHERE id = $1
        """, UUID(session_id))
        
        if not row:
            return {"found": False, "message": "Session not found"}
        
        return {
            "found": True,
            "session": {
                "id": str(row["id"]),
                "contact_id": row["contact_id"],
                "status": row["status"],
                "current_step": row["current_step"],
                "customer_data": json.loads(row["customer_data"]) if row["customer_data"] else {},
                "step_results": json.loads(row["step_results"]) if row["step_results"] else {},
                "chat_history": json.loads(row["chat_history"]) if row["chat_history"] else [],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            }
        }


@mcp.tool()
async def delete_kyc_session(session_id: str) -> dict:
    """Delete a KYC session from database (for cleanup/testing)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM kyc_sessions WHERE id = $1", UUID(session_id))
        deleted_count = int(result.split()[-1]) if result else 0
        
        return {
            "deleted": deleted_count > 0,
            "session_id": session_id,
            "deleted_count": deleted_count
        }


if __name__ == "__main__":
    # Start the HTTP server on port 8001
    import uvicorn
    uvicorn.run(mcp.streamable_http_app, host="127.0.0.1", port=8001)
