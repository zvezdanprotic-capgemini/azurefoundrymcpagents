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
import httpx
from pathlib import Path

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


@mcp.tool()
def convert_url_to_markdown(url: str, timeout_seconds: int = 30) -> dict:
    """
    Download a document from a URL and convert it to markdown if it's a PDF or DOCX.
    
    This tool:
    1. Downloads the document from the provided URL
    2. Detects the file type based on URL extension or Content-Type header
    3. Converts PDF/DOCX/DOC files to markdown using docling
    4. Returns the markdown content and metadata
    
    Supported file types:
    - PDF (.pdf)
    - Microsoft Word (.docx, .doc)
    
    Args:
        url: The URL of the document to download and convert
        timeout_seconds: Maximum time to wait for download (default: 30)
        
    Returns:
        Dict with success status, markdown content, file info, and any error messages
    """
    from mcp_servers.document_processor import convert_to_markdown
    
    try:
        # Download the document
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            file_bytes = response.content
            
            # Determine filename from URL or Content-Disposition header
            filename = Path(url).name
            if "content-disposition" in response.headers:
                content_disp = response.headers["content-disposition"]
                if "filename=" in content_disp:
                    filename = content_disp.split("filename=")[1].strip('"\'')
            
            # Get content type
            content_type = response.headers.get("content-type", "")
            
            # Determine file extension
            ext = Path(filename).suffix.lower()
            
            # If no extension, try to infer from content-type
            if not ext or ext not in ['.pdf', '.docx', '.doc']:
                if 'pdf' in content_type:
                    ext = '.pdf'
                    filename = filename + '.pdf' if not filename.endswith('.pdf') else filename
                elif 'word' in content_type or 'officedocument' in content_type:
                    ext = '.docx'
                    filename = filename + '.docx' if not filename.endswith('.docx') else filename
            
            # Check if file type is supported
            if ext not in ['.pdf', '.docx', '.doc']:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {ext}. Only PDF and Word documents are supported.",
                    "url": url,
                    "detected_extension": ext,
                    "content_type": content_type
                }
            
            # Convert to markdown
            markdown_content = convert_to_markdown(file_bytes, filename)
            
            return {
                "success": True,
                "url": url,
                "filename": filename,
                "file_type": ext,
                "content_type": content_type,
                "file_size_bytes": len(file_bytes),
                "markdown_length": len(markdown_content),
                "markdown": markdown_content
            }
            
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "error": f"HTTP error: {e.response.status_code} - {e.response.reason_phrase}",
            "url": url
        }
    except httpx.RequestError as e:
        return {
            "success": False,
            "error": f"Request error: {str(e)}",
            "url": url
        }
    except ValueError as e:
        return {
            "success": False,
            "error": f"Conversion error: {str(e)}",
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "url": url
        }


if __name__ == "__main__":
    # Start the HTTP server on port 8002
    import uvicorn
    uvicorn.run(mcp.streamable_http_app, host="127.0.0.1", port=8002)
