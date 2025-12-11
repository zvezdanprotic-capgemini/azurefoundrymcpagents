"""
MCP HTTP Application Factory

Creates ASGI applications that properly implement the MCP Streamable HTTP protocol
while also providing health check endpoints for monitoring.

Architecture:
- Uses FastMCP to create MCP-compliant streamable HTTP servers
- Wraps BaseMCPServer instances and registers their tools with FastMCP
- Creates composite ASGI app that routes /health to FastAPI and /mcp to FastMCP
- Ensures compatibility with langchain-mcp-adapters MultiServerMCPClient
"""

from typing import Any, Callable, Dict
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from mcp.server import FastMCP
from mcp import types
import inspect

from .base import BaseMCPServer, ToolResult


def create_mcp_http_app(base_server: BaseMCPServer) -> ASGIApp:
    """
    Creates a proper MCP-compliant ASGI application for a BaseMCPServer.
    
    This function:
    1. Creates a FastMCP instance with the server name
    2. Dynamically registers all tools from BaseMCPServer with FastMCP
    3. Creates tool handlers that bridge BaseMCPServer.call_tool to FastMCP
    4. Generates FastMCP's streamable HTTP app for /mcp endpoint
    5. Creates FastAPI app for /health endpoint
    6. Returns composite ASGI app that routes to appropriate handler
    
    Args:
        base_server: Instance of BaseMCPServer (PostgresMCPServer, BlobMCPServer, etc.)
    
    Returns:
        ASGI application compatible with uvicorn that implements:
        - GET /health -> {"status": "ok", "service": "<server name>"}
        - GET/POST /mcp -> MCP Streamable HTTP protocol (SSE + POST)
    """
    
    # Create FastMCP instance with server configuration
    mcp = FastMCP(
        name=base_server.name,
        instructions=f"MCP server for {base_server.name}",
    )
    
    # Get all tool definitions from the BaseMCPServer
    tool_definitions = base_server.get_tools()
    
    # Register each tool with FastMCP
    for tool_def in tool_definitions:
        tool_name = tool_def["name"]
        tool_description = tool_def.get("description", "")
        input_schema = tool_def.get("inputSchema", {})
        
        # Create a tool handler function that calls the BaseMCPServer's call_tool method
        # We need to create this in a closure to capture the tool_name properly
        def create_tool_handler(captured_tool_name: str) -> Callable:
            """Creates a tool handler closure that captures the tool name."""
            
            async def tool_handler(**arguments: Any) -> str:
                """
                Tool handler that bridges FastMCP to BaseMCPServer.call_tool.
                
                Args:
                    **arguments: Tool arguments passed by MCP client
                
                Returns:
                    String representation of the result for MCP client
                """
                try:
                    # Call the BaseMCPServer's call_tool method
                    result: ToolResult = await base_server.call_tool(
                        captured_tool_name, 
                        arguments
                    )
                    
                    # Check if the call was successful
                    if not result.success:
                        error_msg = result.error or "Unknown error occurred"
                        return f"Error: {error_msg}"
                    
                    # Return the data from the result
                    # Convert to string if it's not already
                    if isinstance(result.data, str):
                        return result.data
                    elif result.data is not None:
                        # For complex data, return JSON string representation
                        import json
                        return json.dumps(result.data, indent=2, default=str)
                    else:
                        return "Success"
                        
                except Exception as e:
                    base_server.logger.error(
                        f"Error executing tool {captured_tool_name}: {e}",
                        exc_info=True
                    )
                    return f"Error executing tool: {str(e)}"
            
            return tool_handler
        
        # Create the handler for this specific tool
        handler = create_tool_handler(tool_name)
        
        # Extract parameter information from input schema
        properties = input_schema.get("properties", {})
        required_params = input_schema.get("required", [])
        
        # Build function signature dynamically
        # Create parameter annotations for the handler
        params = []
        for param_name, param_def in properties.items():
            param_type = str  # Default to str, MCP handles type conversion
            is_required = param_name in required_params
            
            # Create parameter with proper annotation
            if is_required:
                params.append(inspect.Parameter(
                    param_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=param_type
                ))
            else:
                params.append(inspect.Parameter(
                    param_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=None,
                    annotation=param_type
                ))
        
        # Update handler signature
        sig = inspect.Signature(params, return_annotation=str)
        handler.__signature__ = sig  # type: ignore
        handler.__name__ = tool_name
        handler.__doc__ = tool_description or f"Tool: {tool_name}"
        
        # Register the tool with FastMCP using the decorator pattern
        mcp.add_tool(
            handler,
            name=tool_name,
            description=tool_description
        )
        
        base_server.logger.info(f"Registered tool: {tool_name}")
    
    # Create the MCP streamable HTTP ASGI app
    mcp_app = mcp.streamable_http_app()
    
    # Create FastAPI app for health endpoint
    health_app = FastAPI()
    
    @health_app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring."""
        return {
            "status": "ok",
            "service": base_server.name
        }
    
    # Create composite ASGI application that routes requests
    async def composite_asgi_app(scope: Scope, receive: Receive, send: Send) -> None:
        """
        Composite ASGI app that routes requests to appropriate handler.
        
        Routes:
        - /health -> FastAPI health check
        - /mcp -> FastMCP streamable HTTP (MCP protocol)
        - /* -> 404 Not Found
        """
        if scope["type"] == "http":
            path = scope["path"]
            
            if path == "/health":
                # Route to FastAPI health endpoint
                await health_app(scope, receive, send)
            elif path == "/mcp":
                # Route to FastMCP streamable HTTP endpoint
                await mcp_app(scope, receive, send)
            else:
                # Return 404 for unknown paths
                await send({
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [[b"content-type", b"application/json"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"error": "Not Found", "message": "Use /health or /mcp endpoints"}',
                })
        elif scope["type"] == "lifespan":
            # Handle lifespan events (startup/shutdown)
            # Both health_app and mcp_app will handle their own lifespan
            # We'll delegate to mcp_app as it's the primary app
            await mcp_app(scope, receive, send)
        else:
            # For websocket or other types, delegate to mcp_app
            await mcp_app(scope, receive, send)
    
    base_server.logger.info(
        f"Created MCP HTTP app for {base_server.name} with {len(tool_definitions)} tools"
    )
    
    return composite_asgi_app
