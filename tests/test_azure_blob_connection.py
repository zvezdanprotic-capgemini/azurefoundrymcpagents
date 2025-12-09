"""
Test Azure Blob Storage Connection
Tests if the storage account connection string and container are configured correctly.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_azure_blob():
    print("=" * 60)
    print("Testing Azure Blob Storage Connection")
    print("=" * 60)
    
    # Check required env vars
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_BLOB_CONTAINER", "kyc-documents")
    
    # Parse account name from connection string
    account_name = None
    if connection_string:
        for part in connection_string.split(";"):
            if part.startswith("AccountName="):
                account_name = part.split("=", 1)[1]
                break
    
    print(f"\nAccount Name: {account_name or 'NOT FOUND'}")
    print(f"Container: {container_name}")
    print(f"Connection String: {'SET' if connection_string else 'NOT SET'}")
    
    if not connection_string:
        print("\n❌ ERROR: AZURE_STORAGE_CONNECTION_STRING is not set!")
        return False
    
    try:
        from azure.storage.blob import BlobServiceClient
        
        print("\n  Creating BlobServiceClient...")
        client = BlobServiceClient.from_connection_string(connection_string)
        
        # Test connection by getting account info
        account_info = client.get_account_information()
        print(f"✓ Connected! Account kind: {account_info['account_kind']}")
        
        # Check if container exists
        print(f"\n  Checking container '{container_name}'...")
        container_client = client.get_container_client(container_name)
        
        if container_client.exists():
            print(f"✓ Container '{container_name}' exists")
            
            # List some blobs (limit by iterating)
            blobs = []
            for i, blob in enumerate(container_client.list_blobs()):
                if i >= 5:
                    break
                blobs.append(blob)
            print(f"  Found {len(blobs)} blob(s) (showing max 5)")
            for blob in blobs:
                print(f"    - {blob.name} ({blob.size} bytes)")
        else:
            print(f"⚠️  Container '{container_name}' does not exist yet")
            print("   It will be created automatically when first document is uploaded")
        
        print(f"\n✅ SUCCESS! Azure Blob Storage is accessible.")
        return True
        
    except ImportError:
        print("\n❌ ERROR: azure-storage-blob not installed. Run: pip install azure-storage-blob")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_azure_blob()
    sys.exit(0 if success else 1)
