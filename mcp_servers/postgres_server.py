"""
PostgreSQL MCP Server

Provides tools for:
- Looking up customer data from CRM (accounts, contacts, orders)
- Saving and loading KYC session state for long-running workflows
- Accessing customer history (quotes, invoices, previous KYC)
"""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
from mcp_servers.http_app import create_mcp_http_app

from mcp_servers.base import BaseMCPServer, ToolResult, get_env_or_default

logger = logging.getLogger("mcp_servers.postgres")


class PostgresMCPServer(BaseMCPServer):
    """MCP Server for PostgreSQL database operations."""
    
    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        """
        Initialize with optional connection pool.
        If not provided, will create one on first use.
        """
        super().__init__()
        self._pool = pool
    # (removed stray import inside class)
    
    @property
    def name(self) -> str:
        return "postgres"
    
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
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions for this server."""
        return [
            {
                "name": "get_customer_by_email",
                "description": "Look up a customer (contact + account) by their email address",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string", "description": "Customer email address"}
                    },
                    "required": ["email"]
                }
            },
            {
                "name": "get_customer_history",
                "description": "Get a customer's order, quote, and invoice history",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "integer", "description": "Contact ID"},
                        "account_id": {"type": "integer", "description": "Account ID (optional)"}
                    },
                    "required": ["contact_id"]
                }
            },
            {
                "name": "get_previous_kyc_sessions",
                "description": "Get list of previous KYC sessions for a customer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "integer", "description": "Contact ID"}
                    },
                    "required": ["contact_id"]
                }
            },
            {
                "name": "save_kyc_session_state",
                "description": "Save current KYC session state to database for persistence",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Session UUID"},
                        "contact_id": {"type": "integer", "description": "Contact ID (optional)"},
                        "status": {"type": "string", "description": "Session status"},
                        "current_step": {"type": "string", "description": "Current workflow step"},
                        "customer_data": {"type": "object", "description": "Customer information"},
                        "step_results": {"type": "object", "description": "Results from each step"},
                        "chat_history": {
                            "type": "array",
                            "description": "Conversation history",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string"},
                                    "content": {"type": "string"},
                                    "timestamp": {"type": "string"}
                                },
                                "required": ["role", "content"]
                            }
                        }
                    },
                    "required": ["session_id", "status", "current_step", "customer_data"]
                }
            },
            {
                "name": "load_kyc_session_state",
                "description": "Load a saved KYC session state from database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Session UUID"}
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "delete_kyc_session",
                "description": "Delete a KYC session from database (for cleanup/testing)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Session UUID to delete"}
                    },
                    "required": ["session_id"]
                }
            }
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool and return the result."""
        try:
            if tool_name == "get_customer_by_email":
                return await self._get_customer_by_email(arguments["email"])
            elif tool_name == "get_customer_history":
                return await self._get_customer_history(
                    arguments["contact_id"],
                    arguments.get("account_id")
                )
            elif tool_name == "get_previous_kyc_sessions":
                return await self._get_previous_kyc_sessions(arguments["contact_id"])
            elif tool_name == "save_kyc_session_state":
                return await self._save_kyc_session_state(arguments)
            elif tool_name == "load_kyc_session_state":
                return await self._load_kyc_session_state(arguments["session_id"])
            elif tool_name == "delete_kyc_session":
                return await self._delete_kyc_session(arguments["session_id"])
            else:
                return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolResult(success=False, error=str(e))

    async def _get_customer_by_email(self, email: str) -> ToolResult:
        """Look up customer by email."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Get contact with account info
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
                return ToolResult(
                    success=True,
                    data={"found": False, "message": "No customer found with this email"}
                )
            
            customer = {
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
            
            return ToolResult(success=True, data=customer)
    
    async def _get_customer_history(self, contact_id: int, account_id: Optional[int] = None) -> ToolResult:
        """Get customer's order, quote, and invoice history."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # If no account_id provided, get it from contact
            if not account_id:
                row = await conn.fetchrow(
                    "SELECT account_id FROM contacts WHERE id = $1", contact_id
                )
                if row:
                    account_id = row["account_id"]
            
            if not account_id:
                return ToolResult(
                    success=True,
                    data={"orders": [], "quotes": [], "invoices": [], "message": "No account linked"}
                )
            
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
            
            return ToolResult(success=True, data={
                "orders": [dict(r) for r in orders],
                "quotes": [dict(r) for r in quotes],
                "invoices": [dict(r) for r in invoices]
            })
    
    async def _get_previous_kyc_sessions(self, contact_id: int) -> ToolResult:
        """Get previous KYC sessions for a customer."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            sessions = await conn.fetch("""
                SELECT id, status, current_step, created_at, updated_at
                FROM kyc_sessions
                WHERE contact_id = $1
                ORDER BY created_at DESC LIMIT 10
            """, contact_id)
            
            return ToolResult(success=True, data={
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
            })
    
    async def _save_kyc_session_state(self, args: Dict[str, Any]) -> ToolResult:
        """Save KYC session state to database."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            session_id = args["session_id"]
            
            # Upsert session
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
                args.get("contact_id"),
                args["status"],
                args["current_step"],
                json.dumps(args["customer_data"]),
                json.dumps(args.get("step_results", {})),
                json.dumps(args.get("chat_history", []))
            )
            
            return ToolResult(success=True, data={"saved": True, "session_id": session_id})
    
    async def _load_kyc_session_state(self, session_id: str) -> ToolResult:
        """Load KYC session state from database."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, contact_id, status, current_step, customer_data, step_results, chat_history, created_at, updated_at
                FROM kyc_sessions WHERE id = $1
            """, UUID(session_id))
            
            if not row:
                return ToolResult(
                    success=True,
                    data={"found": False, "message": "Session not found"}
                )
            
            return ToolResult(success=True, data={
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
            })
    
    async def _delete_kyc_session(self, session_id: str) -> ToolResult:
        """Delete a KYC session from database."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM kyc_sessions WHERE id = $1",
                UUID(session_id)
            )
            # result format: "DELETE N" where N is count
            deleted_count = int(result.split()[-1]) if result else 0
            
            return ToolResult(success=True, data={
                "deleted": deleted_count > 0,
                "session_id": session_id,
                "deleted_count": deleted_count
            })
    
    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()

# FastAPI app exposing HTTP MCP endpoints (defined after class)
app = create_mcp_http_app(PostgresMCPServer())
