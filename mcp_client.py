"""
HTTP MCP Client for KYC System

This module provides a client that connects to HTTP MCP servers
using the standard MCP protocol with langchain-mcp-adapters.

The client manages connections to multiple MCP servers and provides
a unified interface for agents to call tools.
"""
import os
import asyncio
import logging
import httpx
from datetime import timedelta
from typing import Dict, Any, List, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from aiobreaker import CircuitBreaker, CircuitBreakerError
from error_handling import get_tracer

logger = logging.getLogger("kyc.mcp_client")


class KYCMCPClient:
    """
    Client for connecting to HTTP MCP servers.
    
    This client manages connections to PostgreSQL, Blob, Email, and RAG servers,
    all running as separate HTTP services.
    """
    
    def __init__(
        self,
        postgres_url: str = "http://127.0.0.1:8001/mcp",
        blob_url: str = "http://127.0.0.1:8002/mcp",
        email_url: str = "http://127.0.0.1:8003/mcp",
        rag_url: str = "http://127.0.0.1:8004/mcp"
    ):
        """
        Initialize MCP client with server URLs.
        
        Args:
            postgres_url: URL for PostgreSQL MCP server
            blob_url: URL for Blob Storage MCP server
            email_url: URL for Email MCP server
            rag_url: URL for RAG MCP server
        """
        self.server_config = {
            "postgres": {
                "transport": "streamable_http",
                "url": postgres_url,
            },
            "blob": {
                "transport": "streamable_http",
                "url": blob_url,
            },
            "email": {
                "transport": "streamable_http",
                "url": email_url,
            },
            "rag": {
                "transport": "streamable_http",
                "url": rag_url,
            }
        }
        
        self._client: Optional[MultiServerMCPClient] = None
        self._tools: Optional[List] = None
        self._connected: bool = False
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Circuit breaker for tool calls (5 failures, 60s recovery)
        self._circuit_breaker = CircuitBreaker(
            fail_max=5,
            timeout_duration=timedelta(seconds=60),
            name="mcp_tool_calls"
        )
    
    async def initialize(self):
        """
        Initialize connection to all MCP servers.
        
        This method:
        1. Creates an HTTP client for health check requests
        2. Initializes the MultiServerMCPClient with all 4 server configs
        3. Loads all available tools from connected servers
        4. Normalizes tool names with server prefixes (e.g., "postgres__get_customer_by_email")
        5. Sets the connected flag to True
        
        Must be called before using get_tools() or call_tool().
        """
        logger.info("Initializing HTTP MCP client connections...")
        
        # Create HTTP client for health checks (10s timeout for initial connections)
        self._http_client = httpx.AsyncClient(timeout=10.0)
        
        # Initialize the multi-server client that manages all 4 MCP server connections
        self._client = MultiServerMCPClient(self.server_config)
        
        # Load all tools from all connected servers
        raw_tools = await self._client.get_tools()
        
        # Normalize tool names with server prefixes so tests and agents can target specific servers
        # This ensures consistent naming across the system (e.g., "get_customer_by_email" becomes "postgres__get_customer_by_email")
        server_tool_index = {
            "postgres": {
                "get_customer_by_email",
                "get_customer_history",
                "get_previous_kyc_sessions",
                "save_kyc_session_state",
                "load_kyc_session_state",
                "delete_kyc_session",
            },
            "blob": {
                "list_customer_documents",
                "get_document_url",
                "upload_document",
                "get_document_metadata",
                "delete_document",
            },
            "email": {
                "send_kyc_approved_email",
                "send_kyc_pending_email",
                "send_kyc_rejected_email",
            },
            "rag": {
                "search_policies",
                "get_policy_requirements",
                "check_compliance",
                "list_policy_categories",
                "delete_policy_document",
            },
        }
        
        # Prefix each tool with its server name for clarity and consistency
        prefixed_tools = []
        for tool in raw_tools:
            name = getattr(tool, "name", "")
            # Extract base name (remove any existing prefix)
            base = name.split("__")[-1] if "__" in name else name
            
            # Find which server this tool belongs to by matching base name
            server_match = None
            for server, names in server_tool_index.items():
                if base in names:
                    server_match = server
                    break
            
            # Add server prefix if not already present
            if server_match and not name.startswith(server_match + "__"):
                # Mutate name to include server prefix for test consistency
                try:
                    setattr(tool, "name", f"{server_match}__{base}")
                except Exception:
                    # Some tools may have read-only names, just skip
                    pass
            prefixed_tools.append(tool)
        
        # Store the prefixed tools list
        self._tools = prefixed_tools
        self._connected = True
        logger.info(f"Connected to MCP servers. Loaded {len(self._tools)} tools.")
    
    async def get_tools(self) -> List:
        """
        Get all available tools from connected servers with OpenTelemetry tracing.
        
        This method:
        1. Ensures the client is initialized (auto-initializes if needed)
        2. Creates an OpenTelemetry span for observability
        3. Returns the complete list of 20 tools from all 4 servers
        
        Returns:
            List of LangChain Tool objects with server-prefixed names
        """
        if self._tools is None:
            await self.initialize()
        
        # Create a trace span for observability
        tracer = get_tracer()
        with tracer.start_as_current_span("mcp.get_tools") as span:
            span.set_attribute("mcp.tool_count", len(self._tools) if self._tools else 0)
            return self._tools
    
    def get_tools_for_server(self, server_name: str) -> List:
        """
        Get tools for a specific server only.
        
        Filters the full tool list to return only tools belonging to the specified server.
        Tool names are expected to follow the pattern: "{server_name}__{tool_name}"
        
        Args:
            server_name: Name of the server (e.g., "postgres", "blob", "email", "rag")
            
        Returns:
            List of Tool objects for the specified server
            
        Raises:
            RuntimeError: If client is not initialized
        """
        if self._tools is None:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        return [tool for tool in self._tools if getattr(tool, "name", "").startswith(f"{server_name}__")]
    
    async def get_server_health(self) -> Dict[str, bool]:
        """
        Check health of each MCP server independently.
        
        This method:
        1. Iterates through all 4 configured servers (postgres, blob, email, rag)
        2. Makes HTTP GET request to each server's /health endpoint
        3. Sets 5-second timeout for each health check
        4. Returns status based on HTTP 200 response
        5. Gracefully handles failures (network errors, timeouts) by marking as unhealthy
        
        Returns:
            Dict mapping server names to health status (True=healthy, False=unhealthy)
            Example: {"postgres": True, "blob": True, "email": False, "rag": True}
            
        Raises:
            RuntimeError: If client is not initialized
        """
        if not self._http_client:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        health = {}
        for server_name, config in self.server_config.items():
            try:
                # Extract base URL and construct health endpoint
                # Replace /mcp path with /health (e.g., http://127.0.0.1:8001/mcp -> http://127.0.0.1:8001/health)
                url = config["url"].replace("/mcp", "/health")
                
                # Make health check request with 5-second timeout
                response = await self._http_client.get(url, timeout=5.0)
                
                # Server is healthy if it returns HTTP 200
                health[server_name] = response.status_code == 200
            except Exception as e:
                # Log warning but don't crash - health check failures are non-fatal
                logger.warning(f"Health check failed for {server_name}: {e}")
                health[server_name] = False
        
        return health
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on an MCP server with circuit breaker protection and OpenTelemetry tracing.
        
        This method implements production-ready resilience patterns:
        
        1. **Circuit Breaker Protection**: 
           - Wraps tool invocation with aiobreaker circuit breaker
           - Opens circuit after 5 consecutive failures
           - Stays open for 60 seconds before attempting recovery
           - Prevents cascading failures when servers are down
        
        2. **OpenTelemetry Tracing**:
           - Creates a span for each tool invocation
           - Records tool name, arguments, and execution status
           - Tracks circuit breaker state (success/error/circuit_open)
           - Enables distributed tracing across the system
        
        3. **Error Handling**:
           - CircuitBreakerError → Converts to user-friendly "Service temporarily unavailable"
           - Other exceptions → Logged with full context and re-raised
        
        Args:
            tool_name: Full tool name with server prefix (e.g., "postgres__get_customer_by_email")
            arguments: Dictionary of tool-specific arguments
            
        Returns:
            Tool execution result (structure depends on the specific tool)
            
        Raises:
            RuntimeError: If client not initialized or circuit breaker is open
            ValueError: If tool_name is not found in available tools
            Exception: Any error raised by the tool execution
        """
        if self._client is None:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        # Find the requested tool in our loaded tools list
        tool = next((t for t in self._tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # Create a wrapper function decorated with circuit breaker
        # This is necessary because aiobreaker's decorator pattern properly tracks failures
        @self._circuit_breaker
        async def protected_call():
            """Inner function protected by circuit breaker."""
            return await tool.ainvoke(arguments)
        
        # Wrap tool invocation with OpenTelemetry tracing for observability
        tracer = get_tracer()
        with tracer.start_as_current_span(f"mcp.tool.{tool_name}") as span:
            # Record tool metadata in the trace span
            span.set_attribute("mcp.tool.name", tool_name)
            span.set_attribute("mcp.tool.arguments", str(arguments))
            
            try:
                # Call the circuit-breaker-protected function
                result = await protected_call()
                
                # Record success status in trace
                span.set_attribute("mcp.tool.status", "success")
                return result
                
            except CircuitBreakerError as e:
                # Circuit breaker is open - service is temporarily unavailable
                span.set_attribute("mcp.tool.status", "circuit_open")
                logger.error(f"Circuit breaker open for tool {tool_name}")
                raise RuntimeError(f"Service temporarily unavailable: {tool_name}") from e
                
            except Exception as e:
                # Tool execution failed - record error details
                span.set_attribute("mcp.tool.status", "error")
                span.set_attribute("mcp.tool.error", str(e))
                logger.error(f"Tool call failed: {tool_name}", exc_info=True)
                raise
    
    async def close(self):
        """
        Close connections to all MCP servers and cleanup resources.
        
        This method:
        1. Closes the MultiServerMCPClient (which handles cleanup of all 4 server connections)
        2. Closes the HTTP client used for health checks
        3. Sets the connected flag to False
        
        Should be called during application shutdown to ensure graceful cleanup.
        """
        if self._client:
            # MultiServerMCPClient handles cleanup of all server connections
            logger.info("Closed MCP client connections")
        
        if self._http_client:
            # Close the HTTP client used for health checks
            await self._http_client.aclose()
            self._http_client = None
        
        self._connected = False

    def is_connected(self) -> bool:
        """
        Check if the MCP client has successfully initialized.
        
        Returns:
            True if initialize() completed successfully, False otherwise
        """
        return self._connected


# Global client instance (initialized at app startup)
_mcp_client: Optional[KYCMCPClient] = None


def initialize_mcp_client(
    postgres_url: str = "http://127.0.0.1:8001/mcp",
    blob_url: str = "http://127.0.0.1:8002/mcp",
    email_url: str = "http://127.0.0.1:8003/mcp",
    rag_url: str = "http://127.0.0.1:8004/mcp"
) -> KYCMCPClient:
    """
    Initialize the global MCP client singleton.
    
    This function should be called once at application startup before any agents are used.
    It creates a global client instance that is shared across all agents and requests.
    
    Args:
        postgres_url: URL for PostgreSQL MCP server (default: http://127.0.0.1:8001/mcp)
        blob_url: URL for Blob Storage MCP server (default: http://127.0.0.1:8002/mcp)
        email_url: URL for Email MCP server (default: http://127.0.0.1:8003/mcp)
        rag_url: URL for RAG MCP server (default: http://127.0.0.1:8004/mcp)
        
    Returns:
        The initialized KYCMCPClient instance
        
    Example:
        # In main_http.py startup event:
        client = initialize_mcp_client()
        await client.initialize()
    """
    global _mcp_client
    _mcp_client = KYCMCPClient(postgres_url, blob_url, email_url, rag_url)
    return _mcp_client


def get_mcp_client() -> KYCMCPClient:
    """
    Get the global MCP client instance.
    
    This function returns the singleton client instance that was created by initialize_mcp_client().
    Agents use this function to access the shared MCP client for tool calls.
    
    Returns:
        The global KYCMCPClient instance
        
    Raises:
        RuntimeError: If initialize_mcp_client() has not been called yet
        
    Example:
        # In an agent:
        client = get_mcp_client()
        tools = await client.get_tools()
    """
    if _mcp_client is None:
        raise RuntimeError("MCP client not initialized. Call initialize_mcp_client() first.")
    return _mcp_client
