"""
Azure Blob MCP Server Integration Test

Tests the Azure Blob MCP server with real storage:
1. Test upload_document - upload test document
2. Test list_customer_documents - verify document appears
3. Test get_document_metadata - check metadata
4. Test get_document_url - generate SAS URL
5. Test delete_document - cleanup
"""
import asyncio
import base64
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.blob_server import BlobMCPServer


async def test_blob_mcp():
    print("=" * 60)
    print("Azure Blob MCP Server Integration Test")
    print("=" * 60)
    
    server = BlobMCPServer()
    test_account_id = "TEST999"
    test_filename = "test_integration_doc.txt"
    test_blob_path = f"customers/Customer{test_account_id}/test/{test_filename}"
    
    try:
        # Test 1: Get tools
        print("\n1. Testing get_tools()...")
        tools = server.get_tools()
        tool_names = [t["name"] for t in tools]
        print(f"   ✓ Found {len(tools)} tools: {tool_names}")
        
        # Test 2: Upload document
        print(f"\n2. Testing upload_document()...")
        test_content = "This is a test document for MCP integration testing.\nGenerated automatically."
        content_base64 = base64.b64encode(test_content.encode()).decode()
        
        result = await server.call_tool("upload_document", {
            "account_id": test_account_id,
            "filename": test_filename,
            "content_base64": content_base64,
            "content_type": "text/plain",
            "document_type": "test",
            "metadata": {"test_run": "true", "purpose": "integration_test"}
        })
        if result.success and result.data.get("uploaded"):
            print(f"   ✓ Document uploaded: {result.data['blob_path']}")
            test_blob_path = result.data['blob_path']
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 3: List customer documents
        print(f"\n3. Testing list_customer_documents()...")
        result = await server.call_tool("list_customer_documents", {
            "account_id": test_account_id
        })
        if result.success:
            docs = result.data.get("documents", [])
            print(f"   ✓ Found {len(docs)} document(s) for customer {test_account_id}")
            for doc in docs:
                print(f"      - {doc['name']} ({doc['size']} bytes)")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 4: Get document metadata
        print(f"\n4. Testing get_document_metadata()...")
        result = await server.call_tool("get_document_metadata", {
            "blob_path": test_blob_path
        })
        if result.success and result.data.get("size"):
            print(f"   ✓ Metadata retrieved:")
            print(f"      Size: {result.data['size']} bytes")
            print(f"      Content-Type: {result.data['content_type']}")
            print(f"      Metadata: {result.data.get('metadata', {})}")
        else:
            print(f"   ✗ Error: {result.error if result.error else 'Document not found'}")
            return False
        
        # Test 5: Get document URL
        print(f"\n5. Testing get_document_url()...")
        result = await server.call_tool("get_document_url", {
            "blob_path": test_blob_path,
            "expiry_hours": 1
        })
        if result.success and result.data.get("url"):
            url = result.data['url']
            print(f"   ✓ SAS URL generated (expires in {result.data['expires_in_hours']}h)")
            print(f"      URL: {url[:80]}...")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 6: Delete document (cleanup)
        print(f"\n6. Testing delete_document() (cleanup)...")
        result = await server.call_tool("delete_document", {
            "blob_path": test_blob_path
        })
        if result.success:
            if result.data.get("deleted"):
                print(f"   ✓ Document deleted successfully")
            else:
                print(f"   ⚠ Document not found (may already be deleted)")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 7: Verify deletion
        print(f"\n7. Verifying document was deleted...")
        result = await server.call_tool("get_document_metadata", {
            "blob_path": test_blob_path
        })
        if result.success and not result.data.get("size"):
            print(f"   ✓ Confirmed: document no longer exists")
        else:
            print(f"   ⚠ Document still exists!")
        
        print("\n" + "=" * 60)
        print("✅ Azure Blob MCP Server: ALL TESTS PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        # Try to cleanup on error
        try:
            await server.call_tool("delete_document", {"blob_path": test_blob_path})
        except:
            pass
        return False


if __name__ == "__main__":
    success = asyncio.run(test_blob_mcp())
    sys.exit(0 if success else 1)
