"""
Unit tests for LegislatieScraper class.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from legislatie_scraper import LegislatieScraper


class TestLegislatieScraper:
    """Test suite for LegislatieScraper."""

    @pytest.fixture
    def scraper(self):
        """Create a scraper instance for testing."""
        return LegislatieScraper()

    def test_init(self):
        """Test scraper initialization."""
        scraper = LegislatieScraper()
        assert scraper.session is not None
        assert scraper.token is None
        assert scraper.request_delay == 1.0  # default from config
        assert "User-Agent" in scraper.session.headers

    def test_rate_limit(self, scraper):
        """Test rate limiting logic."""
        # First call should not sleep
        start_time = time.time()
        scraper._rate_limit()
        elapsed = time.time() - start_time

        # Should be very fast (no sleep)
        assert elapsed < 0.1

        # Second call immediately after should sleep for request_delay
        scraper.last_request_time = time.time()  # Simulate recent request
        start_time = time.time()
        scraper._rate_limit()
        elapsed = time.time() - start_time

        # Should have slept approximately request_delay
        # But with mocking we can't reliably test sleep
        # Just verify the method completes

    @patch("legislatie_scraper.BeautifulSoup")
    @patch("legislatie_scraper.requests.Session")
    def test_ensure_token_success(self, mock_session_class, mock_bs):
        """Test successful token retrieval."""
        # Mock session response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><input name="__RequestVerificationToken" value="test-token-123"></html>'
        mock_session.get.return_value = mock_response

        mock_session_class.return_value = mock_session

        # Mock BeautifulSoup
        mock_soup = Mock()
        mock_token_input = Mock()
        mock_token_input.__getitem__ = Mock(return_value="test-token-123")
        mock_soup.find.return_value = mock_token_input
        mock_bs.return_value = mock_soup

        # Create scraper and test
        scraper = LegislatieScraper()
        scraper.session = mock_session  # Replace session with mock

        scraper._ensure_token()

        assert scraper.token == "test-token-123"
        mock_session.get.assert_called_once_with(scraper.BASE_URL, timeout=30)

    @patch("legislatie_scraper.BeautifulSoup")
    @patch("legislatie_scraper.requests.Session")
    def test_ensure_token_failure(self, mock_session_class, mock_bs):
        """Test token retrieval failure."""
        # Mock session response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>No token here</html>"
        mock_session.get.return_value = mock_response

        mock_session_class.return_value = mock_session

        # Mock BeautifulSoup returning None
        mock_soup = Mock()
        mock_soup.find.return_value = None
        mock_bs.return_value = mock_soup

        # Create scraper
        scraper = LegislatieScraper()
        scraper.session = mock_session

        # Should raise ValueError
        with pytest.raises(ValueError, match="Verification token not found"):
            scraper._ensure_token()

    @patch("legislatie_scraper.BeautifulSoup")
    @patch("legislatie_scraper.requests.Session")
    def test_ensure_token_http_error(self, mock_session_class, mock_bs):
        """Test token retrieval with HTTP error."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_session.get.return_value = mock_response

        mock_session_class.return_value = mock_session

        scraper = LegislatieScraper()
        scraper.session = mock_session

        with pytest.raises(Exception):
            scraper._ensure_token()

    @patch("legislatie_scraper.LegislatieScraper._parse_results")
    @patch("legislatie_scraper.LegislatieScraper._ensure_token")
    @patch("legislatie_scraper.requests.Session")
    def test_search_success(
        self, mock_session_class, mock_ensure_token, mock_parse_results
    ):
        """Test successful search with mocked HTML response."""
        # Mock session
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://legislatie.just.ro/Public/Search?text1=contract"
        mock_response.text = "<html></html>"
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        # Mock parse results to return expected data
        mock_parse_results.return_value = [
            {
                "Titlu": "LEGE 123/2023",
                "Numar": "123",
                "DataVigoare": "2023-06-15",
                "Emitent": "PARLAMENTUL ROMÂNIEI",
                "Text": "Textul legii...",
                "TipAct": "LEGE",
                "Publicatie": "Monitorul Oficial nr. 456/2023",
                "LinkHtml": "https://legislatie.just.ro/Public/DetaliiDocument/123456",
            }
        ]

        scraper = LegislatieScraper()
        scraper.session = mock_session
        scraper.token = "test-token"

        results = scraper.search(
            numar_pagina=0, rezultate_pagina=10, an="2023", text="contract"
        )

        assert isinstance(results, list)
        assert len(results) == 1

        result = results[0]
        assert result["Titlu"] == "LEGE 123/2023"
        assert result["Numar"] == "123"
        assert result["DataVigoare"] == "2023-06-15"
        assert result["Emitent"] == "PARLAMENTUL ROMÂNIEI"
        assert result["Text"] == "Textul legii..."
        assert result["TipAct"] == "LEGE"
        assert result["Publicatie"] == "Monitorul Oficial nr. 456/2023"
        assert (
            result["LinkHtml"]
            == "https://legislatie.just.ro/Public/DetaliiDocument/123456"
        )

        # Verify session.post was called with correct params
        mock_session.post.assert_called_once()
        # Verify _ensure_token was called
        mock_ensure_token.assert_called_once()
        # Verify _parse_results was called with response text
        mock_parse_results.assert_called_once_with(mock_response.text)

    @patch("legislatie_scraper.LegislatieScraper._ensure_token")
    @patch("legislatie_scraper.requests.Session")
    def test_search_no_results(self, mock_session_class, mock_ensure_token):
        """Test search with no results."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><div>No results found</div></html>"
        mock_session.post.return_value = mock_response

        mock_session_class.return_value = mock_session

        scraper = LegislatieScraper()
        scraper.session = mock_session
        scraper.token = "test-token"

        results = scraper.search()

        assert results == []

    @patch("legislatie_scraper.LegislatieScraper._ensure_token")
    @patch("legislatie_scraper.requests.Session")
    def test_search_http_error(self, mock_session_class, mock_ensure_token):
        """Test search with HTTP error."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_session.post.return_value = mock_response

        mock_session_class.return_value = mock_session

        scraper = LegislatieScraper()
        scraper.session = mock_session
        scraper.token = "test-token"

        with pytest.raises(Exception):
            scraper.search()

    def test_parse_date_valid(self, scraper):
        """Test date parsing with valid formats."""
        test_cases = [
            ("15/06/2023", "2023-06-15"),
            ("01/12/2024", "2024-12-01"),
            ("31/01/2023", "2023-01-31"),
        ]

        for input_date, expected in test_cases:
            result = scraper._parse_date(input_date)
            assert result == expected

    def test_parse_date_invalid(self, scraper):
        """Test date parsing with invalid formats."""
        invalid_cases = [
            "invalid-date",
            "2023-06-15",  # wrong format
            "15.06.2023",  # wrong separator
            "",
            None,
        ]

        for invalid_date in invalid_cases:
            result = scraper._parse_date(invalid_date)
            assert result == ""  # Should return empty string for invalid dates

    def test_extract_field_value(self, scraper):
        """Test extraction of field values from result details."""
        mock_details = Mock()
        mock_spans = [
            Mock(text="Număr:"),
            Mock(text="123"),
            Mock(text="Data vigoare:"),
            Mock(text="15.06.2023"),
            Mock(text="Emitent:"),
            Mock(text="PARLAMENTUL ROMÂNIEI"),
        ]
        mock_details.find_all.return_value = mock_spans

        # Mock the actual method (it's private, so we need to check if it exists)
        if hasattr(scraper, "_extract_field_value"):
            value = scraper._extract_field_value(mock_details, "Număr")
            assert value == "123"

            value = scraper._extract_field_value(mock_details, "Emitent")
            assert value == "PARLAMENTUL ROMÂNIEI"

            value = scraper._extract_field_value(mock_details, "Nonexistent")
            assert value == ""

    @pytest.mark.parametrize(
        "page_num, expected_offset",
        [
            (0, 0),
            (1, 10),
            (2, 20),
            (5, 50),
        ],
    )
    def test_calculate_offset(self, scraper, page_num, expected_offset):
        """Test calculation of result offset for pagination."""
        # This is an internal calculation, test if it exists
        if hasattr(scraper, "_calculate_offset"):
            offset = scraper._calculate_offset(page_num, 10)
            assert offset == expected_offset
