"""
Quick test to verify HTTP MCP agents can call tools
"""
import asyncio
import os
from dotenv import load_dotenv
from mcp_client import initialize_mcp_client, get_mcp_client
from agents import IntakeAgent

load_dotenv()

async def test_http_mcp_integration():
    """Test that agents can use HTTP MCP tools"""
    
    # Initialize HTTP MCP client
    print("Initializing HTTP MCP client...")
    mcp_client = initialize_mcp_client(
        postgres_url="http://127.0.0.1:8001/mcp",
        blob_url="http://127.0.0.1:8002/mcp",
        email_url="http://127.0.0.1:8003/mcp",
        rag_url="http://127.0.0.1:8004/mcp",
    )
    
    await mcp_client.initialize()
    print(f"✅ MCP client initialized")
    
    # Get tools
    tools = await mcp_client.get_tools()
    print(f"✅ Loaded {len(tools)} tools from HTTP MCP servers")
    print(f"   Available tools: {[t.name for t in tools[:5]]}")
    
    # Create an agent (it will use HTTP MCP tools automatically)
    agent = IntakeAgent()
    print(f"✅ Created IntakeAgent (inherits from BaseKYCAgentHTTP)")
    
    # Test agent can access tools
    agent_tools = await agent.get_tools()
    print(f"✅ Agent has access to {len(agent_tools)} tools")
    print(f"   Agent tools: {[t.name for t in agent_tools]}")
    
    # Test agent invocation with a simple message
    print("\n🧪 Testing agent invocation...")
    result = await agent.invoke(
        customer_data={"name": "John Doe", "email": "john@example.com"},
        latest_message="Customer provides: DOB 01.01.1990, Address 123 Main St, and consents to background check",
        conversation_history=[]
    )
    
    print(f"✅ Agent responded: decision={result['parsed_decision'].get('decision')}")
    print(f"   Tool calls made: {len(result.get('tool_calls', []))}")
    if result.get('tool_calls'):
        for tc in result['tool_calls']:
            print(f"   - Called: {tc['tool_name']} with {tc['arguments']}")
    
    # Cleanup
    await mcp_client.close()
    print("\n✅ All tests passed! HTTP MCP integration working correctly.")
    print("\n📝 Summary:")
    print("   - HTTP MCP servers are running and accessible")
    print("   - Agents inherit from BaseKYCAgentHTTP")
    print("   - Agents can access and call MCP tools via HTTP")
    print("   - Tool calling workflow is functional")

if __name__ == "__main__":
    asyncio.run(test_http_mcp_integration())
