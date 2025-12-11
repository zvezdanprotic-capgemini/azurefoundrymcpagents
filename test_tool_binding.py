"""
Detailed test to verify tool binding to LLM
"""
import asyncio
import os
from dotenv import load_dotenv
from mcp_client import initialize_mcp_client
from agents import IntakeAgent
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

async def test_tool_binding():
    """Test that tools are properly bound to the LLM"""
    
    print("🔍 Testing tool binding to LLM...\n")
    
    # Initialize MCP client
    mcp_client = initialize_mcp_client(
        postgres_url="http://127.0.0.1:8001/mcp",
        blob_url="http://127.0.0.1:8002/mcp",
        email_url="http://127.0.0.1:8003/mcp",
        rag_url="http://127.0.0.1:8004/mcp",
    )
    await mcp_client.initialize()
    
    # Create agent
    agent = IntakeAgent()
    
    # Get tools that should be available to this agent
    tools = await agent.get_tools()
    print(f"✅ Agent has {len(tools)} tools available:")
    for tool in tools:
        print(f"   - {tool.name}: {tool.description[:60]}...")
    
    # Check if LLM has tools bound
    llm_with_tools = agent.llm.bind_tools(tools)
    print(f"\n✅ LLM with tools bound: {type(llm_with_tools)}")
    
    # Test direct LLM invocation with tools
    print(f"\n🧪 Testing LLM invocation with tools...")
    messages = [
        SystemMessage(content="You are a helpful assistant with access to database tools."),
        HumanMessage(content="Can you look up the customer with email john@example.com using the available tools?")
    ]
    
    response = await llm_with_tools.ainvoke(messages)
    
    print(f"\n📊 LLM Response:")
    print(f"   Type: {type(response)}")
    print(f"   Has tool_calls: {hasattr(response, 'tool_calls')}")
    
    if hasattr(response, 'tool_calls') and response.tool_calls:
        print(f"   Tool calls requested: {len(response.tool_calls)}")
        for tc in response.tool_calls:
            print(f"      🔧 {tc['name']} with args: {tc['args']}")
        print("\n✅ SUCCESS: LLM is requesting tool calls!")
        print("   This means agents CAN call MCP tools when configured correctly")
    else:
        print(f"   Content: {response.content[:200]}...")
        print("\n⚠️  LLM did not request tools")
        print("   This might be because:")
        print("   1. The prompt didn't require tools")
        print("   2. Tools not properly bound")
        print("   3. LLM chose to respond without tools")
    
    await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(test_tool_binding())
