
# server/http_math_server.py
"""
Minimal MCP server over Streamable HTTP exposing math tools.
Run:
  python http_math_server.py
Then the server listens on http://127.0.0.1:8000/mcp
"""
from mcp.server.fastmcp import FastMCP

# Use json_response=True for simple JSON responses (no SSE stream)
mcp = FastMCP("MathHTTP", json_response=True)

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

if __name__ == "__main__":
    # Start the Streamable HTTP server; default endpoint is /mcp
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
