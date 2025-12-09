"""
Test Azure OpenAI Connection
Tests if the Azure OpenAI API key, endpoint, and deployment are configured correctly.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_azure_openai():
    print("=" * 60)
    print("Testing Azure OpenAI Connection")
    print("=" * 60)
    
    # Check required env vars
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    
    print(f"\nEndpoint: {endpoint}")
    print(f"Deployment: {deployment}")
    print(f"API Version: {api_version}")
    print(f"API Key: {'*' * 10}...{api_key[-4:] if api_key else 'NOT SET'}")
    
    if not all([endpoint, api_key, deployment]):
        print("\n❌ ERROR: Missing required environment variables!")
        return False
    
    try:
        from openai import AzureOpenAI
        
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        
        print("\n✓ Client created successfully")
        print("  Sending test prompt...")
        
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "user", "content": "Say hello in exactly 5 words."}
            ],
            max_tokens=50
        )
        
        print(f"\n✅ SUCCESS! Response: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_azure_openai()
    sys.exit(0 if success else 1)
