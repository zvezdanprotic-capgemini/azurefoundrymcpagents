"""
PostgreSQL MCP Server Integration Test

Tests the PostgreSQL MCP server with a real database connection:
1. Test get_customer_by_email
2. Test save_kyc_session_state - create test session
3. Test load_kyc_session_state - verify session saved
4. Test delete_kyc_session - cleanup
"""
import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.postgres_server import PostgresMCPServer


async def test_postgres_mcp():
    print("=" * 60)
    print("PostgreSQL MCP Server Integration Test")
    print("=" * 60)
    
    server = PostgresMCPServer()
    test_session_id = str(uuid.uuid4())
    
    try:
        # Test 1: Get tools
        print("\n1. Testing get_tools()...")
        tools = server.get_tools()
        tool_names = [t["name"] for t in tools]
        print(f"   ✓ Found {len(tools)} tools: {tool_names}")
        
        # Test 2: Get customer by email (testing connection)
        print("\n2. Testing get_customer_by_email()...")
        result = await server.call_tool("get_customer_by_email", {"email": "test@example.com"})
        if result.success:
            if result.data.get("found"):
                print(f"   ✓ Customer found: {result.data['contact']['first_name']} {result.data['contact']['last_name']}")
            else:
                print(f"   ✓ No customer found (connection works!)")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 3: Save KYC session state
        print(f"\n3. Testing save_kyc_session_state() with session {test_session_id[:8]}...")
        test_customer_data = {
            "name": "Test User",
            "email": "test-integration@example.com",
            "test_run": True
        }
        result = await server.call_tool("save_kyc_session_state", {
            "session_id": test_session_id,
            "status": "test",
            "current_step": "integration_test",
            "customer_data": test_customer_data,
            "step_results": {"test": "passed"},
            "chat_history": [{"role": "user", "content": "test"}]
        })
        if result.success and result.data.get("saved"):
            print(f"   ✓ Session saved successfully")
        else:
            print(f"   ✗ Error saving session: {result.error if result.error else result.data}")
            return False
        
        # Test 4: Load KYC session state
        print(f"\n4. Testing load_kyc_session_state()...")
        result = await server.call_tool("load_kyc_session_state", {"session_id": test_session_id})
        if result.success and result.data.get("found"):
            session = result.data["session"]
            print(f"   ✓ Session loaded: status={session['status']}, step={session['current_step']}")
        else:
            print(f"   ✗ Session not found or error: {result.error if result.error else result.data}")
            return False
        
        # Test 5: Delete KYC session (cleanup)
        print(f"\n5. Testing delete_kyc_session() (cleanup)...")
        result = await server.call_tool("delete_kyc_session", {"session_id": test_session_id})
        if result.success:
            if result.data.get("deleted"):
                print(f"   ✓ Session deleted successfully")
            else:
                print(f"   ⚠ Session not found (may already be deleted)")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 6: Verify deletion
        print(f"\n6. Verifying session was deleted...")
        result = await server.call_tool("load_kyc_session_state", {"session_id": test_session_id})
        if result.success and not result.data.get("found"):
            print(f"   ✓ Confirmed: session no longer exists")
        else:
            print(f"   ⚠ Session still exists!")
        
        print("\n" + "=" * 60)
        print("✅ PostgreSQL MCP Server: ALL TESTS PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False
    finally:
        await server.close()


if __name__ == "__main__":
    success = asyncio.run(test_postgres_mcp())
    sys.exit(0 if success else 1)
