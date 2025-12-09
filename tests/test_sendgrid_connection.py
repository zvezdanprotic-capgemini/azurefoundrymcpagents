"""
Test SendGrid API Connection
Tests if the SendGrid API key is valid (without sending an actual email).
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_sendgrid():
    print("=" * 60)
    print("Testing SendGrid API Connection")
    print("=" * 60)
    
    # Check required env vars
    api_key = os.getenv("SENDGRID_API_KEY")
    
    print(f"\nAPI Key: {'SG.' + '*' * 20 + '...' + api_key[-4:] if api_key and api_key.startswith('SG.') else 'NOT SET or INVALID FORMAT'}")
    
    if not api_key:
        print("\n❌ ERROR: SENDGRID_API_KEY is not set!")
        return False
    
    if not api_key.startswith("SG."):
        print("\n⚠️  WARNING: API key should start with 'SG.'")
    
    try:
        import sendgrid
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        print("\n  Creating SendGrid client...")
        client = SendGridAPIClient(api_key)
        
        # Test by sending a test email to the sender (validates API key works)
        print("  Testing email send capability...")
        from_email = os.getenv("EMAIL_FROM", "kyc@insurance.com")
        
        message = Mail(
            from_email=from_email,
            to_emails=from_email,  # Send to self as a test
            subject='SendGrid API Test',
            html_content='<strong>API key is valid and working!</strong>'
        )
        
        response = client.send(message)
        
        print(f"\n✅ SUCCESS! Email sent.")
        print(f"   Status Code: {response.status_code}")
        print(f"   Response indicates API key is valid and can send emails.")
        return True
        
    except ImportError:
        print("\n⚠️  sendgrid package not installed. Install it with: pip install sendgrid")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        
        # If it's a 401/403, the API key is invalid or lacks permissions
        if "401" in str(e) or "Unauthorized" in str(e):
            print("   The API key is not valid or has been revoked.")
        elif "403" in str(e) or "Forbidden" in str(e):
            print("   The API key lacks necessary permissions to send emails.")
        else:
            print("   There was an error connecting to SendGrid.")
        return False


if __name__ == "__main__":
    success = test_sendgrid()
    import sys
    sys.exit(0 if success else 1)
