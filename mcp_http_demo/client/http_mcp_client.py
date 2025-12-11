
# client/http_mcp_client.py
"""
Minimal MCP client that connects to the HTTP server and calls tools.
Run:
  python http_mcp_client.py
Ensure the server is running first.
"""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "http://127.0.0.1:8000/mcp"

async def main():
    async with streamablehttp_client(MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Available tools:", [t.name for t in tools.tools])

            res = await session.call_tool("add", {"a": 3, "b": 5})
            # Tool outputs can be structured; for simple int results FastMCP wraps them
            print("add(3,5) =>", res.output)

            res2 = await session.call_tool("multiply", {"a": 8, "b": 12})
            print("multiply(8,12) =>", res2.output)

if __name__ == "__main__":
    asyncio.run(main())
