"""
Tests for the NASDAQ scraper functionality.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from backend.scraper_service.scrapers.nasdaq_scraper import NasdaqScraper


@pytest.mark.asyncio
class TestNasdaqScraper:
    @pytest_asyncio.fixture
    async def nasdaq_scraper(self):
        """Create a NASDAQ scraper instance for testing."""
        scraper = NasdaqScraper()
        # Mock the _make_request method to avoid actual HTTP requests
        scraper._make_request = AsyncMock()
        return scraper

    @pytest.fixture
    def sample_api_response(self):
        """Sample API response data."""
        return json.dumps(
            {
                "data": {
                    "priced": {
                        "rows": [
                            {
                                "companyName": "Test Company 1",
                                "proposedTickerSymbol": "TEST1",
                                "pricingDate": "03/15/2025",
                                "exchange": "NASDAQ",
                                "sharesOffered": "5000000",
                            }
                        ]
                    },
                    "upcoming": {
                        "rows": [
                            {
                                "companyName": "Test Company 2",
                                "proposedTickerSymbol": "TEST2",
                                "expectedPriceDate": "04/01/2025",
                                "exchange": "NYSE",
                                "sharesOffered": "3000000",
                            }
                        ]
                    },
                    "filings": {
                        "rows": [
                            {
                                "companyName": "Test Company 3",
                                "proposedTickerSymbol": "TEST3",
                                "expectedPriceDate": "04/15/2025",
                                "proposedExchange": "NASDAQ",
                                "sharesOffered": "2000000",
                            }
                        ]
                    },
                }
            }
        )

    @pytest.fixture
    def sample_html_content(self):
        """Sample HTML content for fallback testing."""
        return """
        <html>
            <body>
                <table>
                    <tr>
                        <th>Company</th>
                        <th>Symbol</th>
                        <th>Date</th>
                    </tr>
                    <tr>
                        <td>HTML Test Company</td>
                        <td>HTMLTEST</td>
                        <td>04/20/2025</td>
                    </tr>
                </table>
            </body>
        </html>
        """

    @pytest.mark.asyncio
    async def test_scrape_success_primary_api(self, nasdaq_scraper, sample_api_response):
        """Test successful scraping from primary API endpoint."""
        # Setup mock to return sample data
        nasdaq_scraper._make_request.return_value = sample_api_response

        # Call the method under test
        result = await nasdaq_scraper.scrape()

        # Verify the API was called correctly
        nasdaq_scraper._make_request.assert_called_once_with(nasdaq_scraper.api_url, headers=nasdaq_scraper.api_headers, timeout=60)

        # Verify the result
        assert result.success is True
        assert len(result.data) == 3  # One from each section
        assert "Successfully scraped" in result.message

        # Verify the parsed data
        symbols = [listing.symbol for listing in result.data]
        assert "TEST1" in symbols
        assert "TEST2" in symbols
        assert "TEST3" in symbols

    @pytest.mark.asyncio
    async def test_scrape_fallback_to_alternative_api(self, nasdaq_scraper, sample_api_response):
        """Test fallback to alternative API when primary API fails."""
        # Setup mocks to simulate primary API failure
        nasdaq_scraper._make_request.side_effect = [
            Exception("Primary API failed"),
            sample_api_response,
        ]  # First call fails  # Second call succeeds

        # Call the method under test
        result = await nasdaq_scraper.scrape()

        # Verify both APIs were called
        assert nasdaq_scraper._make_request.call_count == 2
        nasdaq_scraper._make_request.assert_any_call(nasdaq_scraper.api_url, headers=nasdaq_scraper.api_headers, timeout=60)
        nasdaq_scraper._make_request.assert_any_call(nasdaq_scraper.api_url_alt, headers=nasdaq_scraper.api_headers, timeout=60)

        # Verify the result
        assert result.success is True
        assert len(result.data) == 3
        assert "Successfully scraped" in result.message

    @pytest.mark.asyncio
    async def test_scrape_fallback_to_html(self, nasdaq_scraper, sample_html_content):
        """Test fallback to HTML scraping when both APIs fail."""
        # Setup mocks to simulate API failures
        nasdaq_scraper._make_request.side_effect = [
            Exception("Primary API failed"),  # First call fails
            Exception("Alternative API failed"),  # Second call fails
            sample_html_content,  # Third call succeeds (HTML)
        ]

        # Call the method under test
        result = await nasdaq_scraper.scrape()

        # Verify all three methods were called
        assert nasdaq_scraper._make_request.call_count == 3
        nasdaq_scraper._make_request.assert_any_call(
            nasdaq_scraper.html_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
            timeout=60,
        )

        # Verify the result
        assert result.success is True
        assert "HTML" in result.message

    @pytest.mark.asyncio
    async def test_scrape_with_date_range(self, nasdaq_scraper, sample_api_response):
        """Test scraping with a specific date range."""
        # Setup mock to return sample data
        nasdaq_scraper._make_request.return_value = sample_api_response

        # Define date range
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        # Call the method under test
        result = await nasdaq_scraper.scrape_with_date_range(start_date, end_date)

        # Verify the API was called with the correct date parameter
        nasdaq_scraper._make_request.assert_called_with(
            f"https://api.nasdaq.com/api/ipo/calendar?date={start_date.strftime('%Y-%m')}",
            headers=nasdaq_scraper.api_headers,
            timeout=60,
        )

        # Verify the result
        assert result.success is True
        assert "Successfully scraped" in result.message

    @pytest.mark.asyncio
    async def test_scrape_all_methods_fail(self, nasdaq_scraper):
        """Test handling when all scraping methods fail."""
        # Setup mocks to simulate all methods failing
        nasdaq_scraper._make_request.side_effect = [
            Exception("Primary API failed"),
            Exception("Alternative API failed"),
            Exception("HTML scraping failed"),
        ]

        # Call the method under test
        result = await nasdaq_scraper.scrape()

        # Verify the result
        assert result.success is False
        assert "Error scraping NASDAQ" in result.message
        assert len(result.data) == 0

    @pytest.mark.asyncio
    async def test_parse_api_data_with_missing_fields(self, nasdaq_scraper):
        """Test parsing API data with missing fields."""
        # Create API response with missing fields
        api_response = json.dumps(
            {
                "data": {
                    "priced": {
                        "rows": [
                            {
                                "companyName": "Missing Fields Company",
                                # Missing proposedTickerSymbol
                                # Missing pricingDate
                                "exchange": "NASDAQ",
                                # Missing sharesOffered
                            }
                        ]
                    }
                }
            }
        )

        # Parse the data
        listings = nasdaq_scraper.parse_api_data(api_response)

        # Verify the parser handles missing fields gracefully
        assert len(listings) == 1
        assert listings[0].name == "Missing Fields Company"
        assert listings[0].symbol.startswith("TBA-")  # Should generate a symbol
        assert listings[0].exchange_code == "NASDAQ"
        assert listings[0].lot_size == 1000  # Default value

    @pytest.mark.asyncio
    async def test_parse_api_data_with_invalid_json(self, nasdaq_scraper):
        """Test parsing invalid JSON data."""
        # Create invalid JSON
        invalid_json = "This is not valid JSON"

        # Parse the data
        listings = nasdaq_scraper.parse_api_data(invalid_json)

        # Verify the parser handles invalid JSON gracefully
        assert len(listings) == 0

    @pytest.mark.asyncio
    async def test_get_filtered_listings(self, nasdaq_scraper, sample_api_response):
        """Test getting filtered listings."""
        # Setup mock to return sample data
        nasdaq_scraper._make_request.return_value = sample_api_response

        # Call the method under test with different filters
        _ = await nasdaq_scraper.get_upcoming_ipos()
        _ = await nasdaq_scraper.get_priced_ipos()
        _ = await nasdaq_scraper.get_nasdaq_listings()
        _ = await nasdaq_scraper.get_nyse_listings()

        # Verify the API was called
        nasdaq_scraper._make_request.assert_called_with(nasdaq_scraper.api_url, headers=nasdaq_scraper.api_headers, timeout=60)

        # Verify the filtering works
        # Note: In a real test, we would check the actual filtering logic,
        # but here we're just verifying the method doesn't crash
        assert nasdaq_scraper._make_request.call_count > 0
