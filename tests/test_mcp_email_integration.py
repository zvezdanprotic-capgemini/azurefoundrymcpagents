"""
Email MCP Server Integration Test

Tests the Email MCP server:
1. Verify SendGrid API key is valid
2. Test email tools exist
3. Test mock email sending (doesn't send real email by default)
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.email_server import EmailMCPServer


async def test_email_mcp():
    print("=" * 60)
    print("Email MCP Server Integration Test")
    print("=" * 60)
    
    server = EmailMCPServer()
    
    try:
        # Test 1: Get tools
        print("\n1. Testing get_tools()...")
        tools = server.get_tools()
        tool_names = [t["name"] for t in tools]
        print(f"   ✓ Found {len(tools)} tools: {tool_names}")
        
        # Test 2: Check configuration
        print("\n2. Checking email configuration...")
        sendgrid_key = os.environ.get("SENDGRID_API_KEY")
        smtp_host = os.environ.get("SMTP_HOST")
        
        if sendgrid_key and sendgrid_key.startswith("SG."):
            print(f"   ✓ SendGrid API key configured")
        elif smtp_host:
            print(f"   ✓ SMTP configured: {smtp_host}")
        else:
            print(f"   ⚠ No email provider configured (will use mock mode)")
        
        # Test 3: Email send (approval email)
        print("\n3. Testing send_kyc_approved_email...")
        result = await server.call_tool("send_kyc_approved_email", {
            "to_email": "test@example.com",
            "customer_name": "Test User"
        })
        if result.success:
            sent = result.data.get("sent", False)
            provider = result.data.get("provider", result.data.get("mode", "unknown"))
            if sent:
                status = result.data.get("status_code", "N/A")
                print(f"   ✓ Email sent via {provider} (Status: {status})")
                print(f"      To: {result.data.get('to')}")
            else:
                print(f"   ✓ Mock mode - Email not actually sent")
                print(f"      Would send to: {result.data.get('to')}")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 4: Pending email
        print("\n4. Testing send_kyc_pending_email...")
        result = await server.call_tool("send_kyc_pending_email", {
            "to_email": "test@example.com",
            "customer_name": "Test User",
            "reason": "Additional documents required"
        })
        if result.success:
            sent = result.data.get("sent", False)
            status_text = "sent" if sent else "mock"
            print(f"   ✓ Pending email {status_text}")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 5: Rejection email
        print("\n5. Testing send_kyc_rejected_email...")
        result = await server.call_tool("send_kyc_rejected_email", {
            "to_email": "test@example.com",
            "customer_name": "Test User",
            "rejection_reasons": ["Age requirement not met", "Missing documentation"]
        })
        if result.success:
            sent = result.data.get("sent", False)
            status_text = "sent" if sent else "mock"
            print(f"   ✓ Rejection email {status_text}")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        # Test 6: Follow-up email
        print("\n6. Testing send_follow_up_email...")
        result = await server.call_tool("send_follow_up_email", {
            "to_email": "test@example.com",
            "customer_name": "Test User",
            "required_documents": ["Proof of address", "Photo ID"]
        })
        if result.success:
            print(f"   ✓ Follow-up email sent in '{result.data.get('mode', 'unknown')}' mode")
        else:
            print(f"   ✗ Error: {result.error}")
            return False
        
        print("\n" + "=" * 60)
        print("✅ Email MCP Server: ALL TESTS PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_email_mcp())
    sys.exit(0 if success else 1)
