
# agent/langgraph_agent_http.py
"""
LangGraph agent that loads MCP tools from the local HTTP server using
langchain-mcp-adapters and answers questions that trigger those tools.

Usage:
  export OPENAI_API_KEY=...  # or set in your environment
  python langgraph_agent_http.py
"""
import asyncio
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

async def main():
    # Connect to the MCP server over HTTP/Streamable HTTP
    client = MultiServerMCPClient({
        "math": {
            "transport": "http",
            "url": "http://127.0.0.1:8000/mcp",
        }
    })

    tools = await client.get_tools()  # Load tools from all configured servers

    # Use a lightweight OpenAI model (customize as needed)
    llm = ChatOpenAI(model="gpt-4o-mini")
    agent = create_react_agent(llm, tools)

    # Ask a question that should trigger math tools
    response = await agent.ainvoke({"messages": "What's (3 + 5) x 12?"})
    print(response["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(main())
