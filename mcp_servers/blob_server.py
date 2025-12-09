"""
Azure Blob Storage MCP Server

Provides tools for:
- Listing customer documents
- Getting document download URLs (SAS)
- Uploading new documents
- Getting document metadata
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
    from azure.core.exceptions import ResourceNotFoundError
    AZURE_BLOB_AVAILABLE = True
except ImportError:
    AZURE_BLOB_AVAILABLE = False
    BlobServiceClient = None

from mcp_servers.base import BaseMCPServer, ToolResult, get_env_or_default

logger = logging.getLogger("mcp_servers.blob")


class BlobMCPServer(BaseMCPServer):
    """MCP Server for Azure Blob Storage operations."""
    
    def __init__(self, connection_string: Optional[str] = None, container_name: Optional[str] = None):
        """
        Initialize with optional connection string and container name.
        If not provided, will use environment variables.
        """
        super().__init__()
        self._connection_string = connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self._container_name = container_name or get_env_or_default("AZURE_BLOB_CONTAINER", "kyc-documents")
        self._client: Optional[BlobServiceClient] = None
    
    @property
    def name(self) -> str:
        return "blob"
    
    def _get_client(self) -> BlobServiceClient:
        """Get or create blob service client."""
        if self._client is None:
            if not self._connection_string:
                raise ValueError("AZURE_STORAGE_CONNECTION_STRING is required")
            self._client = BlobServiceClient.from_connection_string(self._connection_string)
        return self._client
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions for this server."""
        return [
            {
                "name": "list_customer_documents",
                "description": "List all documents for a customer from Azure Blob Storage. Documents are stored in customers/Customer<account_id>/",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string", "description": "Customer account ID (used to build folder path)"},
                        "document_type": {"type": "string", "description": "Filter by type (id, address, consent, etc.)"}
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "get_document_url",
                "description": "Get a temporary SAS URL for downloading a document",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "blob_path": {"type": "string", "description": "Full blob path (customer_id/filename)"},
                        "expiry_hours": {"type": "integer", "description": "URL expiry in hours (default 1)"}
                    },
                    "required": ["blob_path"]
                }
            },
            {
                "name": "upload_document",
                "description": "Upload a document to Azure Blob Storage. Documents are stored in customers/Customer<account_id>/",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string", "description": "Customer account ID (used to build folder path)"},
                        "filename": {"type": "string", "description": "Document filename"},
                        "content_base64": {"type": "string", "description": "Base64 encoded file content"},
                        "content_type": {"type": "string", "description": "MIME type (e.g., application/pdf)"},
                        "document_type": {"type": "string", "description": "Type: id, address, consent, etc."},
                        "metadata": {"type": "object", "description": "Additional metadata"}
                    },
                    "required": ["account_id", "filename", "content_base64"]
                }
            },
            {
                "name": "get_document_metadata",
                "description": "Get metadata for a document without downloading it",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "blob_path": {"type": "string", "description": "Full blob path (customer_id/filename)"}
                    },
                    "required": ["blob_path"]
                }
            },
            {
                "name": "delete_document",
                "description": "Delete a document from Azure Blob Storage (for cleanup/testing)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "blob_path": {"type": "string", "description": "Full blob path to delete"}
                    },
                    "required": ["blob_path"]
                }
            }
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool and return the result."""
        try:
            if tool_name == "list_customer_documents":
                return await self._list_customer_documents(
                    arguments["account_id"],
                    arguments.get("document_type")
                )
            elif tool_name == "get_document_url":
                return await self._get_document_url(
                    arguments["blob_path"],
                    arguments.get("expiry_hours", 1)
                )
            elif tool_name == "upload_document":
                return await self._upload_document(arguments)
            elif tool_name == "get_document_metadata":
                return await self._get_document_metadata(arguments["blob_path"])
            elif tool_name == "delete_document":
                return await self._delete_document(arguments["blob_path"])
            else:
                return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolResult(success=False, error=str(e))
    
    async def _list_customer_documents(self, account_id: str, document_type: Optional[str] = None) -> ToolResult:
        """List all documents for a customer."""
        client = self._get_client()
        container_client = client.get_container_client(self._container_name)
        
        # Documents are stored as: customers/Customer<account_id>/document_type/filename
        customer_folder = f"customers/Customer{account_id}"
        prefix = f"{customer_folder}/"
        if document_type:
            prefix = f"{customer_folder}/{document_type}/"
        
        documents = []
        blobs = container_client.list_blobs(name_starts_with=prefix, include=["metadata"])
        
        for blob in blobs:
            doc = {
                "name": blob.name,
                "size": blob.size,
                "created": blob.creation_time.isoformat() if blob.creation_time else None,
                "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                "content_type": blob.content_settings.content_type if blob.content_settings else None,
                "metadata": blob.metadata or {}
            }
            documents.append(doc)
        
        return ToolResult(success=True, data={
            "account_id": account_id,
            "folder": customer_folder,
            "document_count": len(documents),
            "documents": documents
        })
    
    async def _get_document_url(self, blob_path: str, expiry_hours: int = 1) -> ToolResult:
        """Generate a SAS URL for document download."""
        client = self._get_client()
        
        # Parse account info from connection string for SAS generation
        # Note: In production, use managed identity or stored access policies
        account_name = None
        account_key = None
        
        for part in self._connection_string.split(";"):
            if part.startswith("AccountName="):
                account_name = part.split("=", 1)[1]
            elif part.startswith("AccountKey="):
                account_key = part.split("=", 1)[1]
        
        if not account_name or not account_key:
            return ToolResult(success=False, error="Could not parse storage account credentials")
        
        # Generate SAS token
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self._container_name,
            blob_name=blob_path,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
        )
        
        url = f"https://{account_name}.blob.core.windows.net/{self._container_name}/{blob_path}?{sas_token}"
        
        return ToolResult(success=True, data={
            "url": url,
            "expires_in_hours": expiry_hours,
            "blob_path": blob_path
        })
    
    async def _upload_document(self, args: Dict[str, Any]) -> ToolResult:
        """Upload a document to blob storage."""
        import base64
        
        client = self._get_client()
        container_client = client.get_container_client(self._container_name)
        
        account_id = args["account_id"]
        filename = args["filename"]
        document_type = args.get("document_type", "other")
        
        # Build blob path: customers/Customer<account_id>/document_type/filename
        customer_folder = f"customers/Customer{account_id}"
        blob_path = f"{customer_folder}/{document_type}/{filename}"
        
        # Decode content
        content = base64.b64decode(args["content_base64"])
        
        # Prepare metadata
        metadata = args.get("metadata", {})
        metadata["document_type"] = document_type
        metadata["uploaded_at"] = datetime.utcnow().isoformat()
        
        # Upload
        blob_client = container_client.get_blob_client(blob_path)
        blob_client.upload_blob(
            content,
            overwrite=True,
            content_settings=ContentSettings(content_type=args.get("content_type", "application/octet-stream")),
            metadata=metadata
        )
        
        return ToolResult(success=True, data={
            "uploaded": True,
            "blob_path": blob_path,
            "size": len(content)
        })
    
    async def _get_document_metadata(self, blob_path: str) -> ToolResult:
        """Get metadata for a document."""
        client = self._get_client()
        container_client = client.get_container_client(self._container_name)
        blob_client = container_client.get_blob_client(blob_path)
        
        try:
            properties = blob_client.get_blob_properties()
            return ToolResult(success=True, data={
                "blob_path": blob_path,
                "size": properties.size,
                "content_type": properties.content_settings.content_type,
                "created": properties.creation_time.isoformat() if properties.creation_time else None,
                "last_modified": properties.last_modified.isoformat() if properties.last_modified else None,
                "metadata": properties.metadata or {}
            })
        except ResourceNotFoundError:
            return ToolResult(success=True, data={
                "found": False,
                "blob_path": blob_path,
                "message": "Document not found"
            })
    
    async def _delete_document(self, blob_path: str) -> ToolResult:
        """Delete a document from blob storage."""
        client = self._get_client()
        container_client = client.get_container_client(self._container_name)
        blob_client = container_client.get_blob_client(blob_path)
        
        try:
            blob_client.delete_blob()
            return ToolResult(success=True, data={
                "deleted": True,
                "blob_path": blob_path
            })
        except ResourceNotFoundError:
            return ToolResult(success=True, data={
                "deleted": False,
                "blob_path": blob_path,
                "message": "Document not found"
            })

