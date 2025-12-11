"""
Azure Blob Storage MCP HTTP Server

Exposes Azure Blob Storage tools over HTTP using FastMCP.
Run: python -m mcp_http_servers.blob_http_server

Server listens on http://127.0.0.1:8002/mcp
"""
import os
import base64
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

try:
    from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
    from azure.core.exceptions import ResourceNotFoundError
    AZURE_BLOB_AVAILABLE = True
except ImportError:
    AZURE_BLOB_AVAILABLE = False

# Load environment variables
load_dotenv()

# Create FastMCP server with JSON response mode
mcp = FastMCP("BlobKYC", json_response=True)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse
    return JSONResponse({
        "service": "Azure Blob MCP Server",
            "status": "ok",
        "port": 8002
    })


# Global client
_client = None
_container_name = os.getenv("AZURE_BLOB_CONTAINER", "kyc-documents")
_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")


def get_client():
    """Get or create blob service client."""
    global _client
    if _client is None:
        if not _connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is required")
        _client = BlobServiceClient.from_connection_string(_connection_string)
    return _client


@mcp.tool()
def list_customer_documents(account_id: str, document_type: Optional[str] = None) -> dict:
    """
    List all documents for a customer from Azure Blob Storage.
    Documents are stored in customers/Customer<account_id>/
    """
    client = get_client()
    container_client = client.get_container_client(_container_name)
    
    customer_folder = f"customers/Customer{account_id}"
    prefix = f"{customer_folder}/"
    if document_type:
        prefix = f"{customer_folder}/{document_type}/"
    
    documents = []
    blobs = container_client.list_blobs(name_starts_with=prefix, include=["metadata"])
    
    for blob in blobs:
        documents.append({
            "name": blob.name,
            "size": blob.size,
            "created": blob.creation_time.isoformat() if blob.creation_time else None,
            "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
            "content_type": blob.content_settings.content_type if blob.content_settings else None,
            "metadata": blob.metadata or {}
        })
    
    return {
        "account_id": account_id,
        "folder": customer_folder,
        "document_count": len(documents),
        "documents": documents
    }


@mcp.tool()
def get_document_url(blob_path: str, expiry_hours: int = 1) -> dict:
    """Get a temporary SAS URL for downloading a document."""
    # Parse account info from connection string
    account_name = None
    account_key = None
    
    for part in _connection_string.split(";"):
        if part.startswith("AccountName="):
            account_name = part.split("=", 1)[1]
        elif part.startswith("AccountKey="):
            account_key = part.split("=", 1)[1]
    
    if not account_name or not account_key:
        raise ValueError("Could not parse storage account credentials")
    
    # Generate SAS token
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=_container_name,
        blob_name=blob_path,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
    )
    
    url = f"https://{account_name}.blob.core.windows.net/{_container_name}/{blob_path}?{sas_token}"
    
    return {
        "url": url,
        "expires_in_hours": expiry_hours,
        "blob_path": blob_path
    }


@mcp.tool()
def upload_document(
    account_id: str,
    filename: str,
    content_base64: str,
    document_type: str = "other",
    content_type: str = "application/octet-stream",
    metadata: Optional[dict] = None
) -> dict:
    """
    Upload a document to Azure Blob Storage.
    Documents are stored in customers/Customer<account_id>/document_type/
    """
    client = get_client()
    container_client = client.get_container_client(_container_name)
    
    # Build blob path
    customer_folder = f"customers/Customer{account_id}"
    blob_path = f"{customer_folder}/{document_type}/{filename}"
    
    # Decode content
    content = base64.b64decode(content_base64)
    
    # Prepare metadata
    meta = metadata or {}
    meta["document_type"] = document_type
    meta["uploaded_at"] = datetime.utcnow().isoformat()
    
    # Upload
    blob_client = container_client.get_blob_client(blob_path)
    blob_client.upload_blob(
        content,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
        metadata=meta
    )
    
    return {
        "uploaded": True,
        "blob_path": blob_path,
        "size": len(content)
    }


@mcp.tool()
def get_document_metadata(blob_path: str) -> dict:
    """Get metadata for a document without downloading it."""
    client = get_client()
    container_client = client.get_container_client(_container_name)
    
    try:
        blob_client = container_client.get_blob_client(blob_path)
        properties = blob_client.get_blob_properties()
        
        return {
            "found": True,
            "name": blob_path,
            "size": properties.size,
            "content_type": properties.content_settings.content_type,
            "created": properties.creation_time.isoformat() if properties.creation_time else None,
            "last_modified": properties.last_modified.isoformat() if properties.last_modified else None,
            "metadata": properties.metadata or {}
        }
    except ResourceNotFoundError:
        return {"found": False, "message": "Document not found"}


@mcp.tool()
def delete_document(blob_path: str) -> dict:
    """Delete a document from Azure Blob Storage (for cleanup/testing)."""
    client = get_client()
    container_client = client.get_container_client(_container_name)
    
    try:
        blob_client = container_client.get_blob_client(blob_path)
        blob_client.delete_blob()
        return {"deleted": True, "blob_path": blob_path}
    except ResourceNotFoundError:
        return {"deleted": False, "message": "Document not found"}


if __name__ == "__main__":
    # Start the HTTP server on port 8002
    import uvicorn
    uvicorn.run(mcp.streamable_http_app, host="127.0.0.1", port=8002)
