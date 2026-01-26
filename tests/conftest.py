"""
Pytest configuration and fixtures for Legislatie API Client tests.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import shutil

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ===== FIXTURES FOR EXTERNAL SERVICES =====


@pytest.fixture
def mock_soap_token_response():
    """Mock successful SOAP token response."""
    return "test-token-123456"


@pytest.fixture
def mock_soap_search_response():
    """Mock successful SOAP search response."""
    return {
        "SearchResult": {
            "Legislatie": [
                {
                    "Titlu": "LEGE 123/2023",
                    "Numar": "123",
                    "DataVigoare": "2023-06-15T00:00:00",
                    "Emitent": "PARLAMENTUL ROMÂNIEI",
                    "Text": "Textul legii...",
                    "LinkHtml": "https://legislatie.just.ro/Public/DetaliiDocument/123456",
                    "TipAct": "LEGE",
                    "Publicatie": "Monitorul Oficial nr. 456/2023",
                }
            ]
        }
    }


@pytest.fixture
def mock_soap_error_response():
    """Mock SOAP error response (Solr connection error)."""
    raise Exception("Unable to connect to the remote server")


@pytest.fixture
def mock_html_search_page():
    """Mock HTML search results page (first page)."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Legislatie.just.ro - Căutare</title></head>
    <body>
        <div id="search-results">
            <div class="search-result-item">
                <h3><a href="/Public/DetaliiDocument/123456">LEGE 123/2023</a></h3>
                <div class="result-details">
                    <span class="field-label">Număr:</span> 123<br>
                    <span class="field-label">Data vigoare:</span> 15.06.2023<br>
                    <span class="field-label">Emitent:</span> PARLAMENTUL ROMÂNIEI<br>
                    <span class="field-label">Tip act:</span> LEGE<br>
                    <span class="field-label">Publicație:</span> Monitorul Oficial nr. 456/2023<br>
                </div>
                <div class="result-text">
                    Textul legii...
                </div>
            </div>
        </div>
        <div class="pagination">
            <span class="current-page">Pagina 1 din 5</span>
            <a href="/Public/Search?page=2">Următoarea</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_html_document_page():
    """Mock HTML document detail page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>LEGE 123/2023 - Legislatie.just.ro</title></head>
    <body>
        <div id="document-content">
            <h1>LEGE 123/2023</h1>
            <div class="document-meta">
                <p><strong>Număr:</strong> 123</p>
                <p><strong>Data vigoare:</strong> 15.06.2023</p>
                <p><strong>Emitent:</strong> PARLAMENTUL ROMÂNIEI</p>
                <p><strong>Tip act:</strong> LEGE</p>
                <p><strong>Publicație:</strong> Monitorul Oficial nr. 456/2023</p>
            </div>
            <div class="document-text">
                <p>Textul complet al legii...</p>
                <p>Articolul 1. Dispoziții generale.</p>
                <p>Articolul 2. Aplicare.</p>
            </div>
        </div>
    </body>
    </html>
    """


# ===== FIXTURES FOR CACHE =====


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory for tests."""
    temp_dir = tempfile.mkdtemp(prefix="legislatie_test_cache_")
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_cache():
    """Mock cache instance."""
    cache = Mock()
    cache.get.return_value = None
    cache.set.return_value = True
    cache.delete.return_value = True
    cache.get_stats.return_value = {"hits": 0, "misses": 0, "size": 0}
    return cache


# ===== FIXTURES FOR HTTP REQUESTS =====


@pytest.fixture
def mock_requests_session():
    """Mock requests.Session with common responses."""
    with patch("requests.Session") as mock_session_class:
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>Mock response</html>"
        mock_response.content = b"<html>Mock response</html>"
        mock_session.get.return_value = mock_response
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_zeep_client():
    """Mock zeep.Client for SOAP API tests."""
    with patch("zeep.Client") as mock_client_class:
        mock_client = Mock()
        mock_service = Mock()
        mock_binding = Mock()

        # Mock GetToken method
        mock_binding.GetToken.return_value = "test-token-123"

        # Mock Search method
        mock_search_result = Mock()
        mock_search_result.SearchResult = Mock()
        mock_search_result.SearchResult.Legislatie = [
            Mock(
                Titlu="LEGE 123/2023",
                Numar="123",
                DataVigoare="2023-06-15T00:00:00",
                Emitent="PARLAMENTUL ROMÂNIEI",
                Text="Textul legii...",
                LinkHtml="https://legislatie.just.ro/Public/DetaliiDocument/123456",
                TipAct="LEGE",
                Publicatie="Monitorul Oficial nr. 456/2023",
            )
        ]
        mock_binding.Search.return_value = mock_search_result

        mock_client.service = mock_service
        mock_client.wsdl.services = [Mock(bindings=[mock_binding])]
        mock_client_class.return_value = mock_client

        yield mock_client


# ===== FIXTURES FOR CONFIGURATION =====


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for configuration."""
    with patch.dict(
        "os.environ",
        {
            "LEGISLATIE_WSDL_URL": "https://test.local/wsdl",
            "LEGISLATIE_SOAP_ENDPOINT": "https://test.local/soap",
            "LEGISLATIE_BASE_URL": "https://test.local",
            "LEGISLATIE_REQUEST_DELAY": "0.1",  # Faster for tests
            "LEGISLATIE_MAX_RETRIES": "1",
            "LEGISLATIE_CACHE_TTL": "60",
            "LEGISLATIE_USE_PERSISTENT_CACHE": "false",
            "LEGISLATIE_LOG_LEVEL": "WARNING",
        },
    ):
        yield


# ===== FIXTURES FOR ASYNC TESTING =====


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ===== TEST CONFIGURATION =====


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires network)"
    )
    config.addinivalue_line("markers", "slow: mark test as slow")


# Command line options removed to avoid duplicate registration
# Use pytest.ini markers for test categorization
