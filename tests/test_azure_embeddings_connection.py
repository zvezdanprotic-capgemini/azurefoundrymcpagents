"""
Test Azure OpenAI Embeddings Connection
Tests if the embeddings deployment is configured correctly.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_azure_embeddings():
    print("=" * 60)
    print("Testing Azure OpenAI Embeddings Connection")
    print("=" * 60)
    
    # Check required env vars
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    
    print(f"\nEndpoint: {endpoint}")
    print(f"Embeddings Deployment: {embedding_deployment}")
    print(f"API Version: {api_version}")
    print(f"API Key: {'*' * 10}...{api_key[-4:] if api_key else 'NOT SET'}")
    
    if not all([endpoint, api_key, embedding_deployment]):
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
        print("  Creating test embedding...")
        
        response = client.embeddings.create(
            model=embedding_deployment,
            input="This is a test text for embedding."
        )
        
        embedding = response.data[0].embedding
        print(f"\n✅ SUCCESS! Embedding created.")
        print(f"   Dimensions: {len(embedding)}")
        print(f"   First 5 values: {embedding[:5]}")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_azure_embeddings()
    sys.exit(0 if success else 1)
