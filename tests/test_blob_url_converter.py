"""
Test blob HTTP server's convert_url_to_markdown tool
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx


@pytest.fixture
def mock_pdf_response():
    """Mock a successful PDF download response"""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.content = b"%PDF-1.4 mock pdf content"
    response.headers = {
        "content-type": "application/pdf",
        "content-length": "1024"
    }
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_docx_response():
    """Mock a successful DOCX download response"""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.content = b"PK\x03\x04 mock docx content"
    response.headers = {
        "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "content-disposition": 'attachment; filename="document.docx"'
    }
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_convert_to_markdown():
    """Mock the convert_to_markdown function"""
    with patch('mcp_servers.document_processor.convert_to_markdown') as mock:
        mock.return_value = "# Test Document\n\nThis is the converted markdown content."
        yield mock


def test_convert_url_to_markdown_pdf(mock_pdf_response, mock_convert_to_markdown):
    """Test converting a PDF from URL to markdown"""
    from mcp_http_servers.blob_http_server import convert_url_to_markdown
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_pdf_response
        mock_client_class.return_value = mock_client
        
        # Test with a PDF URL
        result = convert_url_to_markdown("https://example.com/document.pdf")
        
        assert result["success"] is True
        assert result["filename"] == "document.pdf"
        assert result["file_type"] == ".pdf"
        assert "markdown" in result
        assert result["markdown"] == "# Test Document\n\nThis is the converted markdown content."
        assert result["file_size_bytes"] == len(mock_pdf_response.content)
        
        # Verify convert_to_markdown was called
        mock_convert_to_markdown.assert_called_once()
        args = mock_convert_to_markdown.call_args[0]
        assert args[0] == mock_pdf_response.content
        assert args[1] == "document.pdf"


def test_convert_url_to_markdown_docx(mock_docx_response, mock_convert_to_markdown):
    """Test converting a DOCX from URL to markdown"""
    from mcp_http_servers.blob_http_server import convert_url_to_markdown
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_docx_response
        mock_client_class.return_value = mock_client
        
        # Test with a DOCX URL
        result = convert_url_to_markdown("https://example.com/report.docx")
        
        assert result["success"] is True
        assert result["filename"] == "document.docx"  # From Content-Disposition
        assert result["file_type"] == ".docx"
        assert "markdown" in result
        assert result["markdown_length"] > 0


def test_convert_url_to_markdown_no_extension(mock_pdf_response, mock_convert_to_markdown):
    """Test converting a URL without file extension - infers from content-type"""
    from mcp_http_servers.blob_http_server import convert_url_to_markdown
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_pdf_response
        mock_client_class.return_value = mock_client
        
        # Test with a URL without extension
        result = convert_url_to_markdown("https://example.com/download?id=123")
        
        assert result["success"] is True
        assert result["file_type"] == ".pdf"
        assert result["filename"].endswith(".pdf")


def test_convert_url_to_markdown_unsupported_type():
    """Test with unsupported file type"""
    from mcp_http_servers.blob_http_server import convert_url_to_markdown
    
    unsupported_response = Mock(spec=httpx.Response)
    unsupported_response.status_code = 200
    unsupported_response.content = b"text content"
    unsupported_response.headers = {
        "content-type": "text/plain"
    }
    unsupported_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = unsupported_response
        mock_client_class.return_value = mock_client
        
        result = convert_url_to_markdown("https://example.com/file.txt")
        
        assert result["success"] is False
        assert "Unsupported file type" in result["error"]


def test_convert_url_to_markdown_http_error():
    """Test handling of HTTP errors"""
    from mcp_http_servers.blob_http_server import convert_url_to_markdown
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        
        # Simulate 404 error
        error_response = Mock()
        error_response.status_code = 404
        error_response.reason_phrase = "Not Found"
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "404", request=Mock(), response=error_response
        )
        mock_client_class.return_value = mock_client
        
        result = convert_url_to_markdown("https://example.com/missing.pdf")
        
        assert result["success"] is False
        assert "HTTP error: 404" in result["error"]


def test_convert_url_to_markdown_network_error():
    """Test handling of network errors"""
    from mcp_http_servers.blob_http_server import convert_url_to_markdown
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.side_effect = httpx.RequestError("Connection timeout")
        mock_client_class.return_value = mock_client
        
        result = convert_url_to_markdown("https://example.com/document.pdf")
        
        assert result["success"] is False
        assert "Request error" in result["error"]


def test_convert_url_to_markdown_conversion_error(mock_pdf_response):
    """Test handling of conversion errors"""
    from mcp_http_servers.blob_http_server import convert_url_to_markdown
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_pdf_response
        mock_client_class.return_value = mock_client
        
        with patch('mcp_servers.document_processor.convert_to_markdown') as mock_convert:
            mock_convert.side_effect = ValueError("Invalid PDF format")
            
            result = convert_url_to_markdown("https://example.com/corrupt.pdf")
            
            assert result["success"] is False
            assert "Conversion error" in result["error"]


def test_convert_url_to_markdown_custom_timeout(mock_pdf_response, mock_convert_to_markdown):
    """Test custom timeout parameter"""
    from mcp_http_servers.blob_http_server import convert_url_to_markdown
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_pdf_response
        mock_client_class.return_value = mock_client
        
        # Test with custom timeout
        result = convert_url_to_markdown("https://example.com/large.pdf", timeout_seconds=60)
        
        # Verify Client was called with correct timeout
        mock_client_class.assert_called_once_with(timeout=60, follow_redirects=True)
        assert result["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
