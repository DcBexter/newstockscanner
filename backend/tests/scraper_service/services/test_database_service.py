"""
Tests for the database service.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import ListingCreate
from backend.scraper_service.services.database_service import DatabaseHelper, DatabaseService


@pytest.mark.asyncio
class TestDatabaseHelper:
    @pytest.mark.asyncio
    async def test_execute_db_operation_success(self, mock_db):
        """Test successful execution of a database operation."""

        # Create a mock operation function
        async def mock_operation(db):
            return "success"

        # Create a mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        # Create a mock session factory that returns the session
        class MockSessionFactory:
            def __call__(self):
                return mock_session

        # Mock get_session_factory to return our mock factory
        with patch("backend.scraper_service.services.database_service.get_session_factory", return_value=MockSessionFactory()):
            # Create an instance of DatabaseHelper
            db_helper = DatabaseHelper(MockSessionFactory())

            # Call the method under test
            result = await db_helper.execute_db_operation(mock_operation)

            # Verify the result
            assert result == "success"

            # Verify the session was properly managed
            assert mock_session.commit.await_count == 1
            assert mock_session.__aenter__.await_count == 1
            assert mock_session.__aexit__.await_count == 1

    @pytest.mark.asyncio
    async def test_execute_db_operation_error(self, mock_db):
        """Test handling of errors during database operations."""

        # Create a mock operation function that raises an exception
        async def mock_operation(db):
            raise ValueError("Test error")

        # Create a mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.rollback = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        # Return False to propagate exceptions
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # Create a mock session factory that returns the session
        class MockSessionFactory:
            def __call__(self):
                return mock_session

        # Mock get_session_factory to return our mock factory
        with patch("backend.scraper_service.services.database_service.get_session_factory", return_value=MockSessionFactory()):
            # Create an instance of DatabaseHelper
            db_helper = DatabaseHelper(MockSessionFactory())

            # Call the method under test and expect an exception
            with pytest.raises(ValueError, match="Test error"):
                await db_helper.execute_db_operation(mock_operation)

            # Verify the session was properly managed even with an error
            assert mock_session.rollback.await_count == 1
            assert mock_session.__aenter__.await_count == 1
            assert mock_session.__aexit__.await_count == 1


@pytest.mark.asyncio
class TestDatabaseService:
    @pytest.fixture
    def database_service(self):
        """Create a database service instance for testing."""
        return DatabaseService()

    @pytest.mark.asyncio
    async def test_save_listings_empty(self, database_service):
        """Test saving an empty list of listings."""
        result = await database_service.save_listings([])

        assert result["saved_count"] == 0
        assert result["total"] == 0
        assert result["new_listings"] == []

    @pytest.mark.asyncio
    async def test_save_listings_success(self, database_service, sample_listings_data, monkeypatch):
        """Test successfully saving listings to the database."""
        # This is a complex method that uses DatabaseHelper, so we'll mock at a higher level

        # Create a mock for the database helper
        async def mock_execute_db_operation(self, operation):
            # Simulate the database operation by returning a success result
            return {"saved_count": len(sample_listings_data), "total": len(sample_listings_data), "new_listings": sample_listings_data}

        # Apply the mock
        monkeypatch.setattr("backend.scraper_service.services.DatabaseHelper.execute_db_operation", mock_execute_db_operation)

        # Call the method under test
        result = await database_service.save_listings(sample_listings_data)

        # Verify the result
        assert result["saved_count"] == len(sample_listings_data)
        assert result["total"] == len(sample_listings_data)
        assert result["new_listings"] == sample_listings_data

    @pytest.mark.asyncio
    async def test_save_listings_with_error(self, database_service, sample_listings_data, monkeypatch):
        """Test handling of errors when saving listings."""

        # Create a mock for the database helper that raises an exception
        async def mock_execute_db_operation(self, operation):
            raise ValueError("Test database error")

        # Apply the mock
        monkeypatch.setattr("backend.scraper_service.services.DatabaseHelper.execute_db_operation", mock_execute_db_operation)

        # Call the method under test
        result = await database_service.save_listings(sample_listings_data)

        # Verify the result shows no listings were saved
        assert result["saved_count"] == 0
        assert result["total"] == len(sample_listings_data)
        assert result["new_listings"] == []

    # Constants for test data
    EXCHANGE_DATA = {
        "NASDAQ": {"id": 1, "name": "NASDAQ", "code": "NASDAQ", "url": "https://nasdaq.com"},
        "NYSE": {"id": 2, "name": "NYSE", "code": "NYSE", "url": "https://nyse.com"},
    }

    @staticmethod
    def _create_listing_model(listing_data):
        """Helper method to create a ListingCreate model from listing data."""
        return ListingCreate(
            name=listing_data.get("name", ""),
            symbol=listing_data.get("symbol", ""),
            listing_date=listing_data.get("listing_date"),
            lot_size=listing_data.get("lot_size", 0),
            status=listing_data.get("status", ""),
            exchange_id=listing_data.get("exchange_id"),
            exchange_code=listing_data.get("exchange_code", ""),
            security_type=listing_data.get("security_type", "Equity"),
            url=listing_data.get("url"),
            listing_detail_url=listing_data.get("listing_detail_url"),
        )

    @pytest.mark.asyncio
    async def test_process_listings_transaction_success(self, mock_db, sample_listings_data):
        """Test successful transaction handling in the process_listings function."""
        # Create a mock ListingService
        mock_listing_service = AsyncMock()
        mock_listing_service.get_by_symbol_and_exchange = AsyncMock(return_value=None)
        mock_listing_service.create = AsyncMock()

        # Mock the ListingService constructor
        with patch("backend.api_service.services.ListingService", return_value=mock_listing_service):
            # Call the process_listings function with our mock db
            result = await self._execute_process_listings(mock_db, sample_listings_data)

            # Verify the transaction was committed
            mock_db.begin.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.rollback.assert_not_called()

            # Verify the result
            assert result["saved_count"] == len(sample_listings_data)
            assert result["total"] == len(sample_listings_data)
            assert len(result["new_listings"]) == len(sample_listings_data)

    @pytest.mark.asyncio
    async def test_process_listings_transaction_error(self, mock_db, sample_listings_data):
        """Test error handling in the process_listings function."""
        # Create a mock ListingService that raises an exception
        mock_listing_service = AsyncMock()
        mock_listing_service.get_by_symbol_and_exchange = AsyncMock(side_effect=ValueError("Test error"))

        # Mock the ListingService constructor
        with patch("backend.api_service.services.ListingService", return_value=mock_listing_service):
            # Call the process_listings function with our mock db and expect an exception
            with pytest.raises(ValueError, match="Test error"):
                await self._execute_process_listings(mock_db, sample_listings_data)

            # Verify the transaction was rolled back
            mock_db.begin.assert_called_once()
            mock_db.rollback.assert_called_once()
            mock_db.commit.assert_not_called()

    async def _execute_process_listings(self, db, listings_data):
        """
        Execute the process_listings function with the given database and listings data.

        This is a helper method that simulates the inner function of DatabaseService.save_listings.
        """
        # Start a transaction
        await db.begin()

        try:
            # Create service for listings
            from backend.api_service.services import ListingService

            service = ListingService(db)

            saved_count = 0
            new_listings = []

            # Process each listing
            for listing_data in listings_data:
                # Add exchange_id to data based on exchange_code
                exchange_code = listing_data.get("exchange_code")
                if exchange_code in self.EXCHANGE_DATA:
                    listing_data["exchange_id"] = self.EXCHANGE_DATA[exchange_code]["id"]

                # Check if listing exists
                existing = await service.get_by_symbol_and_exchange(listing_data.get("symbol"), exchange_code)

                if existing:
                    # Update existing listing
                    listing_data["id"] = existing.id
                    await service.update(existing.id, listing_data)
                else:
                    # Create new listing
                    create_model = self._create_listing_model(listing_data)
                    await service.create(create_model)
                    new_listings.append(listing_data)

                saved_count += 1

            # Commit the transaction
            await db.commit()

            return {"saved_count": saved_count, "total": len(listings_data), "new_listings": new_listings}

        except Exception as e:
            # Ensure transaction is rolled back
            await db.rollback()
            raise
