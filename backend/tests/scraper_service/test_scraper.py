"""
Tests for the stock scanner functionality.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from backend.core.models import ListingBase, ScrapingResult
from backend.scraper_service.scraper import StockScanner


@pytest.mark.asyncio
class TestStockScanner:
    @pytest_asyncio.fixture
    async def stock_scanner(self):
        """Create a stock scanner instance for testing."""
        scanner = StockScanner()
        # Mock the dependencies
        scanner.db_service = AsyncMock()
        scanner.notification_service = AsyncMock()

        # Mock the scraper classes
        for name, scraper_class in scanner.scraper_classes.items():
            scanner.scraper_classes[name] = MagicMock()

        yield scanner

    @pytest.mark.asyncio
    async def test_scan_listings_all_exchanges(self, stock_scanner, sample_listings_data):
        """Test scanning listings from all exchanges."""
        # Convert sample data to ListingBase objects
        sample_listings = [ListingBase(**item) for item in sample_listings_data]

        # Mock the scraper instances
        for name, mock_class in stock_scanner.scraper_classes.items():
            # Create a mock instance that will be returned by the class constructor
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None

            # Set up the scrape method to return success with sample data
            mock_instance.scrape.return_value = ScrapingResult(success=True, message=f"Successfully scraped {name}", data=sample_listings)

            # Make the mock class return the mock instance
            mock_class.return_value = mock_instance

        # Call the method under test
        result = await stock_scanner.scan_listings()

        # Verify the results
        assert len(result) == len(stock_scanner.scraper_classes) * len(sample_listings_data)

        # Verify each scraper was called
        for name, mock_class in stock_scanner.scraper_classes.items():
            mock_class.assert_called_once()
            mock_instance = mock_class.return_value
            mock_instance.scrape.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_listings_with_filter(self, stock_scanner, sample_listings_data):
        """Test scanning listings with an exchange filter."""
        # Convert sample data to ListingBase objects
        sample_listings = [ListingBase(**item) for item in sample_listings_data]

        # Mock the scraper instances
        for name, mock_class in stock_scanner.scraper_classes.items():
            # Create a mock instance that will be returned by the class constructor
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None

            # Set up the scrape method to return success with sample data
            mock_instance.scrape.return_value = ScrapingResult(success=True, message=f"Successfully scraped {name}", data=sample_listings)

            # Make the mock class return the mock instance
            mock_class.return_value = mock_instance

        # Call the method under test with a filter
        result = await stock_scanner.scan_listings(exchange_filter="nasdaq")

        # Verify the results
        assert len(result) == len(sample_listings_data)  # Only one exchange

        # Verify only the filtered scraper was called
        nasdaq_mock = stock_scanner.scraper_classes["nasdaq"]
        nasdaq_mock.assert_called_once()

        # Verify other scrapers were not called
        for name, mock_class in stock_scanner.scraper_classes.items():
            if name != "nasdaq":
                mock_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_to_database(self, stock_scanner, sample_listings_data):
        """Test saving listings to the database."""
        # Mock the database service
        stock_scanner.db_service.save_listings = AsyncMock(
            return_value={"saved_count": len(sample_listings_data), "total": len(sample_listings_data), "new_listings": sample_listings_data}
        )

        # Call the method under test
        result = await stock_scanner.save_to_database(sample_listings_data)

        # Verify the database service was called correctly
        stock_scanner.db_service.save_listings.assert_called_once_with(sample_listings_data)

        # Verify the result
        assert result["saved_count"] == len(sample_listings_data)
        assert result["new_listings"] == sample_listings_data

    @pytest.mark.asyncio
    async def test_send_notifications(self, stock_scanner, sample_listings_data):
        """Test sending notifications for new listings."""
        # Mock the notification service
        stock_scanner.notification_service.send_listing_notifications = AsyncMock(return_value=True)

        # Call the method under test
        result = await stock_scanner.send_notifications(sample_listings_data)

        # Verify the notification service was called correctly
        stock_scanner.notification_service.send_listing_notifications.assert_called_once_with(sample_listings_data)

        # Verify the result
        assert result is True

    @pytest.mark.asyncio
    async def test_scan_and_process_exchanges(self, stock_scanner, sample_listings_data):
        """Test the full scan and process workflow."""
        # Mock the component methods
        stock_scanner.scan_listings = AsyncMock(return_value=sample_listings_data)
        stock_scanner.save_to_database = AsyncMock(
            return_value={"saved_count": len(sample_listings_data), "total": len(sample_listings_data), "new_listings": sample_listings_data}
        )
        stock_scanner.check_and_notify_unnotified = AsyncMock(return_value=0)
        stock_scanner.send_notifications = AsyncMock(return_value=True)

        # Call the method under test
        result = await stock_scanner.scan_and_process_exchanges()

        # Verify the component methods were called
        stock_scanner.scan_listings.assert_called_once_with(None)
        stock_scanner.save_to_database.assert_called_once_with(sample_listings_data)
        stock_scanner.check_and_notify_unnotified.assert_called_once()
        stock_scanner.send_notifications.assert_called_once_with(sample_listings_data)

        # Verify the result
        assert result["all_listings"] == len(sample_listings_data)
        assert result["saved_count"] == len(sample_listings_data)
        assert result["new_listings"] == len(sample_listings_data)
        assert result["unnotified_sent"] == 0

    @pytest.mark.asyncio
    async def test_check_and_notify_unnotified(self, stock_scanner, monkeypatch):
        """Test checking and notifying about previously unnotified listings."""
        # This is a complex method that uses DatabaseHelper, so we'll mock at a higher level

        # Create a mock for the database helper
        async def mock_execute_db_operation(self, operation):
            # Simulate the database operation by calling the function with a mock db
            mock_db = AsyncMock()
            return 2  # Return 2 unnotified listings processed

        # Apply the mock
        monkeypatch.setattr("backend.scraper_service.services.DatabaseHelper.execute_db_operation", mock_execute_db_operation)

        # Call the method under test
        result = await stock_scanner.check_and_notify_unnotified()

        # Verify the result
        assert result == 2
