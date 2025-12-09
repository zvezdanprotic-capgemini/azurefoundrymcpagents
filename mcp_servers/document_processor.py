"""
Document Processor Service

Handles conversion of PDF/Word documents to Markdown using docling,
then chunks, embeds, and stores them in the vector database.
"""

import os
import logging
import tempfile
import asyncpg
from typing import Optional, Tuple, List
from pathlib import Path
from datetime import datetime
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from docling.document_converter import DocumentConverter

logger = logging.getLogger("mcp_servers.document_processor")


def convert_to_markdown(file_bytes: bytes, filename: str) -> str:
    """
    Convert PDF or Word document to Markdown using docling.
    
    Args:
        file_bytes: Raw bytes of the document
        filename: Original filename (used to determine file type)
        
    Returns:
        Markdown string of the document content
        
    Raises:
        ValueError: If file type is not supported
    """
    from docling.document_converter import DocumentConverter
    
    # Determine file extension
    ext = Path(filename).suffix.lower()
    if ext not in ['.pdf', '.docx', '.doc']:
        raise ValueError(f"Unsupported file type: {ext}. Supported: .pdf, .docx, .doc")
    
    # Write to temporary file (docling requires file path)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    
    try:
        # Convert using docling
        converter = DocumentConverter()
        result = converter.convert(tmp_path)
        
        # Export to markdown
        markdown_content = result.document.export_to_markdown()
        
        logger.info(f"Converted {filename} to markdown ({len(markdown_content)} chars)")
        return markdown_content
        
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {tmp_path}: {e}")


async def process_document(
    pool: asyncpg.Pool,
    embeddings: AzureOpenAIEmbeddings,
    file_bytes: bytes,
    filename: str,
    category: str = "general",
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> Tuple[int, str]:
    """
    Full document processing pipeline:
    1. Convert PDF/Word to Markdown
    2. Chunk the text
    3. Generate embeddings
    4. Store in database with status tracking
    
    Args:
        pool: Database connection pool
        embeddings: Embeddings model
        file_bytes: Raw document bytes
        filename: Original filename
        category: Document category for filtering
        chunk_size: Maximum characters per chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        Tuple of (chunk_count, status)
        
    Raises:
        Exception: If processing fails
    """
    # First, insert a placeholder record to track status
    async with pool.acquire() as conn:
        # Check if document already exists
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM policy_documents WHERE filename = $1",
            filename
        )
        if existing > 0:
            # Delete existing chunks before re-processing
            await conn.execute(
                "DELETE FROM policy_documents WHERE filename = $1",
                filename
            )
            logger.info(f"Deleted {existing} existing chunks for {filename}")
    
    try:
        # Step 1: Convert to Markdown
        logger.info(f"Converting {filename} to markdown...")
        markdown_content = convert_to_markdown(file_bytes, filename)
        
        if not markdown_content.strip():
            raise ValueError("Document conversion produced empty content")
        
        # Step 2: Chunk the text
        logger.info(f"Chunking {filename} with size={chunk_size}, overlap={chunk_overlap}...")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        chunks = splitter.split_text(markdown_content)
        
        if not chunks:
            raise ValueError("Text splitting produced no chunks")
        
        logger.info(f"Created {len(chunks)} chunks from {filename}")
        
        # Step 3: Generate embeddings
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        chunk_embeddings = await embeddings.aembed_documents(chunks)
        
        # Step 4: Store in database
        logger.info(f"Storing {len(chunks)} chunks in database...")
        async with pool.acquire() as conn:
            for i, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
                await conn.execute("""
                    INSERT INTO policy_documents (filename, category, content, chunk_index, embedding)
                    VALUES ($1, $2, $3, $4, $5::vector)
                """, filename, category, chunk, i, str(embedding))
        
        logger.info(f"Successfully processed {filename}: {len(chunks)} chunks indexed")
        return len(chunks), "indexed"
        
    except Exception as e:
        logger.error(f"Error processing document {filename}: {e}")
        raise


async def get_document_list(pool: asyncpg.Pool) -> list:
    """
    Get list of all documents with their chunk counts.
    
    Returns:
        List of document summaries with filename, category, chunk_count, uploaded_at
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                MIN(id) AS document_id,
                filename,
                category,
                COUNT(*) as chunk_count,
                MIN(uploaded_at) as uploaded_at
            FROM policy_documents
            GROUP BY filename, category
            ORDER BY MIN(uploaded_at) DESC
        """)
        
        return [
            {
                "id": row["document_id"],
                "filename": row["filename"],
                "category": row["category"],
                "chunk_count": row["chunk_count"],
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                "status": "indexed"
            }
            for row in rows
        ]


async def get_document_details(pool: asyncpg.Pool, filename: str) -> Optional[dict]:
    """
    Get details for a specific document.
    
    Returns:
        Document details or None if not found
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                filename,
                category,
                COUNT(*) as chunk_count,
                MIN(uploaded_at) as uploaded_at,
                SUM(LENGTH(content)) as total_chars
            FROM policy_documents
            WHERE filename = $1
            GROUP BY filename, category
        """, filename)
        
        if not row:
            return None
        
        # Get sample chunks
        chunks = await conn.fetch("""
            SELECT chunk_index, LEFT(content, 200) as preview
            FROM policy_documents
            WHERE filename = $1
            ORDER BY chunk_index
            LIMIT 5
        """, filename)
        
        return {
            "filename": row["filename"],
            "category": row["category"],
            "chunk_count": row["chunk_count"],
            "total_chars": row["total_chars"],
            "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
            "status": "indexed",
            "sample_chunks": [
                {"index": c["chunk_index"], "preview": c["preview"]}
                for c in chunks
            ]
        }


async def get_document_chunks(pool: asyncpg.Pool, filename: str) -> List[dict]:
    """
    Get all chunks for a specific document.
    
    Returns:
        List of all chunks with their content and metadata
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                chunk_index,
                content,
                category,
                uploaded_at,
                LENGTH(content) as char_count
            FROM policy_documents
            WHERE filename = $1
            ORDER BY chunk_index
        """, filename)
        
        return [
            {
                "index": row["chunk_index"],
                "content": row["content"],
                "category": row["category"],
                "char_count": row["char_count"],
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None
            }
            for row in rows
        ]


async def get_document_details_by_id(pool: asyncpg.Pool, document_id: int) -> Optional[dict]:
    """
    Get document details using a representative chunk row ID.
    Resolves the filename, then aggregates details.
    """
    async with pool.acquire() as conn:
        filename = await conn.fetchval(
            "SELECT filename FROM policy_documents WHERE id = $1",
            document_id,
        )
        if not filename:
            return None

        row = await conn.fetchrow(
            """
            SELECT 
                filename,
                category,
                COUNT(*) as chunk_count,
                MIN(uploaded_at) as uploaded_at,
                SUM(LENGTH(content)) as total_chars
            FROM policy_documents
            WHERE filename = $1
            GROUP BY filename, category
            """,
            filename,
        )

        if not row:
            return None

        chunks = await conn.fetch(
            """
            SELECT chunk_index, LEFT(content, 200) as preview
            FROM policy_documents
            WHERE filename = $1
            ORDER BY chunk_index
            LIMIT 5
            """,
            filename,
        )

        return {
            "id": document_id,
            "filename": row["filename"],
            "category": row["category"],
            "chunk_count": row["chunk_count"],
            "total_chars": row["total_chars"],
            "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
            "status": "indexed",
            "sample_chunks": [
                {"index": c["chunk_index"], "preview": c["preview"]}
                for c in chunks
            ],
        }


async def get_document_chunks_by_id(pool: asyncpg.Pool, document_id: int) -> List[dict]:
    """
    Get all chunks for a document by a representative chunk row ID.
    Resolves the filename first, then selects by filename.
    """
    async with pool.acquire() as conn:
        filename = await conn.fetchval(
            "SELECT filename FROM policy_documents WHERE id = $1",
            document_id,
        )
        if not filename:
            return []

        rows = await conn.fetch(
            """
            SELECT 
                chunk_index,
                content,
                category,
                uploaded_at,
                LENGTH(content) as char_count
            FROM policy_documents
            WHERE filename = $1
            ORDER BY chunk_index
            """,
            filename,
        )

        return [
            {
                "index": row["chunk_index"],
                "content": row["content"],
                "category": row["category"],
                "char_count": row["char_count"],
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
            }
            for row in rows
        ]


async def delete_document(pool: asyncpg.Pool, filename: str) -> int:
    """
    Delete a document and all its chunks.
    
    Returns:
        Number of chunks deleted
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM policy_documents WHERE filename = $1",
            filename
        )
        # result format: "DELETE N"
        deleted_count = int(result.split()[-1]) if result else 0
        logger.info(f"Deleted {deleted_count} chunks for {filename}")
        return deleted_count
