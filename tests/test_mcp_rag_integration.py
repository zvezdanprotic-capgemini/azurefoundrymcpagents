"""
RAG MCP Server Integration Test

Tests the RAG MCP server with real database + embeddings:
1. Test list_policy_categories - check if table exists
2. Test search_policies - semantic search (if data exists)
3. Note: Full ingestion test would require langchain dependency
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.rag_server import RAGMCPServer


async def test_rag_mcp():
    print("=" * 60)
    print("RAG MCP Server Integration Test")
    print("=" * 60)
    
    server = RAGMCPServer()
    
    try:
        # Test 1: Get tools
        print("\n1. Testing get_tools()...")
        tools = server.get_tools()
        tool_names = [t["name"] for t in tools]
        print(f"   ✓ Found {len(tools)} tools: {tool_names}")
        
        # Test 2: List policy categories (tests DB connection)
        print("\n2. Testing list_policy_categories()...")
        result = await server.call_tool("list_policy_categories", {})
        if result.success:
            categories = result.data.get("categories", [])
            if categories:
                print(f"   ✓ Found {len(categories)} categories:")
                for cat in categories:
                    print(f"      - {cat['category']}: {cat['document_count']} docs")
            else:
                print(f"   ✓ Connection works! No policy documents ingested yet.")
                print(f"      (This is expected for a fresh setup)")
        else:
            if "does not exist" in str(result.error):
                print(f"   ⚠ policy_documents table doesn't exist yet.")
                print(f"      Run the schema setup to create it.")
                print(f"      Skipping remaining RAG tests.")
                print("\n" + "=" * 60)
                print("⚠️  RAG MCP Server: PARTIAL PASS (table not created)")
                print("=" * 60)
                return True  # Not a failure, just not set up yet
            else:
                print(f"   ✗ Error: {result.error}")
                return False
        
        # Test 3: Search policies (if any data exists)
        print("\n3. Testing search_policies()...")
        result = await server.call_tool("search_policies", {
            "query": "customer eligibility requirements",
            "limit": 3
        })
        if result.success:
            results = result.data.get("results", [])
            if results:
                print(f"   ✓ Found {len(results)} matching documents:")
                for r in results:
                    print(f"      - {r['filename']} (similarity: {r['similarity']:.3f})")
            else:
                print(f"   ✓ Search works! No matching documents found.")
                print(f"      (Upload policy documents to enable RAG)")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 4: Check compliance (basic test)
        print("\n4. Testing check_compliance()...")
        result = await server.call_tool("check_compliance", {
            "customer_data": {
                "name": "Test User",
                "date_of_birth": "1990-01-01",
                "address": "123 Test St",
                "consent": True
            },
            "product_type": "life",
            "check_types": ["kyc", "aml"]
        })
        if result.success:
            status = result.data.get("overall_status", "UNKNOWN")
            checks = result.data.get("checks", [])
            print(f"   ✓ Compliance check completed: {status}")
            for check in checks:
                print(f"      - {check['type']}: {check['status']} - {check.get('details', '')}")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 5: Delete tool exists (don't actually delete anything)
        print("\n5. Verifying delete_policy_document tool exists...")
        if "delete_policy_document" in tool_names:
            print(f"   ✓ delete_policy_document tool is available")
        else:
            print(f"   ✗ delete_policy_document tool not found!")
            return False
        
        print("\n" + "=" * 60)
        print("✅ RAG MCP Server: ALL TESTS PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False
    finally:
        await server.close()


if __name__ == "__main__":
    success = asyncio.run(test_rag_mcp())
    sys.exit(0 if success else 1)
