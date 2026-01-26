"""
Unit tests for LegislatieClient class.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from legislatie_client import LegislatieClient


class TestLegislatieClient:
    """Test suite for LegislatieClient."""

    @pytest.fixture
    def client(self):
        """Create a client instance for testing."""
        return LegislatieClient()

    def test_init(self):
        """Test client initialization."""
        client = LegislatieClient()
        assert LegislatieClient.WSDL_URL is not None
        assert client.scraper is not None
        assert client.cache is not None
        assert client.client is not None

    @patch("legislatie_client.Client")
    def test_get_token_success(self, mock_zeep_client):
        """Test successful token retrieval from SOAP API."""
        # Mock zeep client
        mock_client = Mock()
        mock_service = Mock()
        mock_service.GetToken.return_value = "soap-token-123"
        mock_client.create_service.return_value = mock_service
        mock_zeep_client.return_value = mock_client

        client = LegislatieClient()
        token = client.get_token()

        assert token == "soap-token-123"
        mock_service.GetToken.assert_called_once()

    @patch("legislatie_client.Client")
    def test_get_token_failure(self, mock_zeep_client):
        """Test token retrieval failure."""
        from zeep.exceptions import Fault

        # Mock zeep client
        mock_client = Mock()
        mock_service = Mock()
        mock_service.GetToken.side_effect = Fault("SOAP connection error")
        mock_client.create_service.return_value = mock_service
        mock_zeep_client.return_value = mock_client

        client = LegislatieClient()
        token = client.get_token()

        assert token is None

    @patch("legislatie_client.Client")
    def test_search_soap_success(self, mock_zeep_client):
        """Test successful search via SOAP API."""
        # Mock zeep client
        mock_client = Mock()
        mock_service = Mock()

        # Mock GetToken
        mock_service.GetToken.return_value = "soap-token-123"

        # Mock Search response
        class MockSearchResult:
            def __init__(self):
                self.SearchResult = Mock()
                self.SearchResult.Legi = [
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

        mock_search_result = MockSearchResult()
        mock_service.Search.return_value = mock_search_result

        mock_client.create_service.return_value = mock_service
        mock_zeep_client.return_value = mock_client

        # Mock cache to return None (cache miss)
        with patch("legislatie_client.get_cache") as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get.return_value = None
            mock_cache.generate_search_key.return_value = "dummy-key"
            mock_get_cache.return_value = mock_cache

            client = LegislatieClient()
            results = client.search(
                numar_pagina=0, rezultate_pagina=10, an="2023", text="contract"
            )

            # Verify results
            assert isinstance(results, list)
            assert len(results) == 1

            result = results[0]
            assert result.Titlu == "LEGE 123/2023"
            assert result.Numar == "123"

            # Verify cache.set was called
            mock_cache.set.assert_called_once()

            # Verify SOAP Search was called
            mock_service.Search.assert_called_once()

    @patch("legislatie_client.Client")
    def test_search_cache_hit(self, mock_zeep_client):
        """Test search with cache hit (no SOAP call)."""
        cached_results = [
            {
                "Titlu": "Cached LEGE",
                "Numar": "999",
                "DataVigoare": "2023-01-01T00:00:00",
                "Emitent": "TEST",
                "Text": "Cached text",
                "LinkHtml": "https://example.com",
                "TipAct": "LEGE",
                "Publicatie": "Test",
            }
        ]

        # Mock cache to return cached results
        with patch("legislatie_client.get_cache") as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get.return_value = cached_results
            mock_cache.generate_search_key.return_value = "dummy-key"
            mock_get_cache.return_value = mock_cache

            client = LegislatieClient()
            results = client.search()

            # Should return cached results
            assert results == cached_results

            # Should not call SOAP API Search method
            mock_zeep_client.return_value.create_service.return_value.Search.assert_not_called()

            # Cache should have been checked
            mock_cache.get.assert_called_once()

    @patch("legislatie_client.Client")
    @patch("legislatie_client.LegislatieScraper")
    def test_search_soap_fallback_scraper(self, mock_scraper_class, mock_zeep_client):
        """Test SOAP failure triggers scraper fallback."""
        from zeep.exceptions import Fault

        # Mock zeep client
        mock_client = Mock()
        mock_service = Mock()
        mock_service.GetToken.return_value = "soap-token-123"
        mock_service.Search.side_effect = Fault(
            "Unable to connect to the remote server"
        )
        mock_client.create_service.return_value = mock_service
        mock_zeep_client.return_value = mock_client

        # Mock scraper that returns results
        mock_scraper = Mock()
        mock_scraper.search.return_value = [
            {
                "Titlu": "Scraped LEGE",
                "Numar": "456",
                "DataVigoare": "2023-06-15",
                "Emitent": "SCRAPED",
                "Text": "Scraped text",
                "LinkHtml": "https://legislatie.just.ro/Public/DetaliiDocument/456",
                "TipAct": "LEGE",
                "Publicatie": "Scraped",
            }
        ]
        mock_scraper_class.return_value = mock_scraper

        # Mock cache miss
        with patch("legislatie_client.get_cache") as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get.return_value = None
            mock_cache.generate_search_key.return_value = "dummy-key"
            mock_get_cache.return_value = mock_cache

            client = LegislatieClient()
            client.scraper = mock_scraper  # Replace with mock

            results = client.search()

            # Should return scraper results
            assert len(results) == 1
            assert results[0]["Titlu"] == "Scraped LEGE"

            # Scraper should have been called
            mock_scraper.search.assert_called_once()

            # Cache should have been set with scraper results
            mock_cache.set.assert_called_once()

    @patch("legislatie_client.Client")
    @patch("legislatie_client.LegislatieScraper")
    def test_search_soap_fallback_scraper_cache(
        self, mock_scraper_class, mock_zeep_client
    ):
        """Test that scraper results are cached."""
        from zeep.exceptions import Fault

        # Mock zeep client
        mock_client = Mock()
        mock_service = Mock()
        mock_service.GetToken.return_value = "soap-token-123"
        mock_service.Search.side_effect = Fault(
            "Unable to connect to the remote server"
        )
        mock_client.create_service.return_value = mock_service
        mock_zeep_client.return_value = mock_client

        # Mock scraper
        mock_scraper = Mock()
        mock_scraper.search.return_value = [{"Titlu": "Test"}]
        mock_scraper_class.return_value = mock_scraper

        with patch("legislatie_client.get_cache") as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get.return_value = None
            mock_cache.generate_search_key.return_value = "dummy-key"
            mock_get_cache.return_value = mock_cache

            client = LegislatieClient()
            client.scraper = mock_scraper

            # First call - should use scraper and cache
            results1 = client.search()

            # Second call - should use cache (scraper not called again)
            mock_cache.get.return_value = results1  # Cache now returns results

            results2 = client.search()

            # Both calls should return same results
            assert results1 == results2

            # Scraper should have been called only once
            assert mock_scraper.search.call_count == 1

            # Cache get should have been called twice
            assert mock_cache.get.call_count == 2

    def test_check_health_all_healthy(self):
        """Test health check with all components healthy."""
        client = LegislatieClient()
        # Mock get_token method
        client.get_token = Mock(return_value="test-token")
        # Mock scraper
        mock_scraper = Mock()
        mock_scraper.search.return_value = [{"Titlu": "Test"}]
        client.scraper = mock_scraper
        # Mock cache
        mock_cache = Mock()
        mock_cache.get_stats.return_value = {"hits": 5, "misses": 3, "size": 10}
        client.cache = mock_cache

        health = client.check_health()

        assert health["overall"] == "healthy"
        assert health["soap_api"]["status"] == "healthy"
        assert health["scraper"]["status"] == "healthy"
        assert health["cache"]["status"] == "healthy"

    def test_check_health_soap_unhealthy(self):
        """Test health check with SOAP API unhealthy."""
        client = LegislatieClient()
        # Mock get_token method returning None (SOAP failure)
        client.get_token = Mock(return_value=None)
        # Mock scraper
        mock_scraper = Mock()
        mock_scraper.search.return_value = [{"Titlu": "Test"}]
        client.scraper = mock_scraper
        # Mock cache
        mock_cache = Mock()
        mock_cache.get_stats.return_value = {"hits": 5, "misses": 3, "size": 10}
        client.cache = mock_cache

        health = client.check_health()

        assert health["overall"] == "unhealthy"
        assert health["soap_api"]["status"] == "unhealthy"
        assert health["scraper"]["status"] == "healthy"
        assert health["cache"]["status"] == "healthy"

    def test_check_health_scraper_unhealthy(self):
        """Test health check with scraper unhealthy."""
        client = LegislatieClient()
        # Mock get_token method
        client.get_token = Mock(return_value="test-token")
        # Mock scraper that raises exception
        mock_scraper = Mock()
        mock_scraper.search.side_effect = Exception("Scraper error")
        client.scraper = mock_scraper
        # Mock cache
        mock_cache = Mock()
        mock_cache.get_stats.return_value = {"hits": 5, "misses": 3, "size": 10}
        client.cache = mock_cache

        health = client.check_health()

        assert health["overall"] == "error"
        assert health["soap_api"]["status"] == "healthy"
        assert health["scraper"]["status"] == "error"
        assert health["cache"]["status"] == "healthy"

    def test_check_health_cache_unhealthy(self):
        """Test health check with cache unhealthy."""
        client = LegislatieClient()
        # Mock get_token method
        client.get_token = Mock(return_value="test-token")
        # Mock scraper
        mock_scraper = Mock()
        mock_scraper.search.return_value = [{"Titlu": "Test"}]
        client.scraper = mock_scraper
        # Mock cache that raises exception
        mock_cache = Mock()
        mock_cache.get_stats.side_effect = Exception("Cache error")
        client.cache = mock_cache

        health = client.check_health()

        assert health["overall"] == "error"
        assert health["soap_api"]["status"] == "healthy"
        assert health["scraper"]["status"] == "healthy"
        assert health["cache"]["status"] == "error"

    def test_health_report_structure(self):
        """Test health report has correct structure."""
        client = LegislatieClient()
        # Mock get_token method
        client.get_token = Mock(return_value="test-token")
        # Mock scraper
        mock_scraper = Mock()
        mock_scraper.search.return_value = []
        client.scraper = mock_scraper
        # Mock cache
        mock_cache = Mock()
        mock_cache.get_stats.return_value = {"hits": 0, "misses": 0, "size": 0}
        client.cache = mock_cache

        health = client.check_health()

        # Check structure
        assert "overall" in health
        assert "timestamp" in health
        assert "soap_api" in health
        assert "scraper" in health
        assert "cache" in health

        # Check nested structure
        assert "status" in health["soap_api"]
        assert "details" in health["soap_api"]
        assert "response_time" in health["soap_api"]

        assert "status" in health["scraper"]
        assert "details" in health["scraper"]
        assert "response_time" in health["scraper"]

        assert "status" in health["cache"]
        assert "details" in health["cache"]

    @patch("legislatie_client.Client")
    def test_search_parameters_passed_correctly(self, mock_zeep_client):
        """Test that search parameters are passed correctly to SOAP API."""
        # Mock zeep client
        mock_client = Mock()
        mock_service = Mock()
        mock_service.GetToken.return_value = "token"
        mock_service.Search.return_value = Mock(SearchResult=Mock(Legi=[]))
        mock_client.create_service.return_value = mock_service
        mock_zeep_client.return_value = mock_client

        with patch("legislatie_client.get_cache") as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get.return_value = None
            mock_cache.generate_search_key.return_value = "dummy-key"
            mock_get_cache.return_value = mock_cache

            client = LegislatieClient()

            # Call with various parameters
            client.search(
                numar_pagina=2,
                rezultate_pagina=25,
                an="2023",
                numar="123",
                text="contract de munca",
                titlu="LEGE",
            )

            # Verify Search was called with correct parameters
            mock_service.Search.assert_called_once()
            call_kwargs = mock_service.Search.call_args[1]

            # Check keyword arguments
            assert "tokenKey" in call_kwargs
            assert call_kwargs["tokenKey"] == "token"
            assert "SearchModel" in call_kwargs
            search_params = call_kwargs["SearchModel"]
            assert search_params["NumarPagina"] == 2
            assert search_params["RezultatePagina"] == 25
            assert search_params["SearchAn"] == "2023"
            assert search_params["SearchNumar"] == "123"
            assert search_params["SearchText"] == "contract de munca"
            assert search_params["SearchTitlu"] == "LEGE"
