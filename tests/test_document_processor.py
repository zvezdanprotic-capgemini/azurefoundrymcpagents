
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.document_processor import convert_to_markdown, process_document

# Mock docling to avoid external dependency issues during basic testing
@pytest.fixture
def mock_docling():
    with patch('docling.document_converter.DocumentConverter') as MockConverter:
        converter_instance = MockConverter.return_value
        # Mock the result object structure
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test Document\n\nThis is a test document content."
        converter_instance.convert.return_value = mock_result
        yield MockConverter

@pytest.fixture
def mock_pool():
    pool = MagicMock()  # Not AsyncMock, because acquire() is not a coroutine, it returns a CM
    conn = AsyncMock()
    
    # Mock the context manager returned by acquire()
    cm = MagicMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.side_effect = AsyncMock(return_value=None)  # Must be awaitable? No, side_effect on Mock can be valid
    # Actually __aexit__ should be an AsyncMock itself or return an awaitable.
    # Easiest is to make __aenter__ and __aexit__ AsyncMocks
    
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    
    pool.acquire.return_value = cm
    
    # Mock existing check to return 0 (no existing document)
    conn.fetchval.return_value = 0
    return pool

@pytest.fixture
def mock_embeddings():
    embeddings = AsyncMock()
    embeddings.aembed_documents.return_value = [[0.1, 0.2, 0.3]] * 2  # return dummy embeddings
    return embeddings

def test_convert_to_markdown_mock(mock_docling):
    """Test markdown conversion with mocked docling"""
    file_bytes = b"fake pdf content"
    filename = "test.pdf"
    
    markdown = convert_to_markdown(file_bytes, filename)
    
    assert markdown == "# Test Document\n\nThis is a test document content."
    assert mock_docling.called

def test_convert_to_markdown_invalid_ext():
    """Test validation of file extension"""
    with pytest.raises(ValueError, match="Unsupported file type"):
        convert_to_markdown(b"content", "test.txt")

@pytest.mark.asyncio
async def test_process_document(mock_pool, mock_embeddings, mock_docling):
    """Test full document processing pipeline with mocks"""
    file_bytes = b"fake pdf content"
    filename = "test.pdf"
    
    chunk_count, status = await process_document(
        mock_pool, 
        mock_embeddings, 
        file_bytes, 
        filename, 
        chunk_size=50,
        chunk_overlap=10
    )
    
    assert chunk_count > 0
    assert status == "indexed"
    
    # Verify database interactions
    conn = mock_pool.acquire.return_value.__aenter__.return_value
    assert conn.execute.called
    # Check that INSERT was called
    insert_calls = [c for c in conn.execute.call_args_list if "INSERT INTO policy_documents" in c[0][0]]
    assert len(insert_calls) > 0

