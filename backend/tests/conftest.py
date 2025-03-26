"""
Shared test fixtures for the backend tests.
"""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from backend.config.settings import get_settings
from backend.database.session import get_db

# Settings fixture
@pytest.fixture
def test_settings():
    """Return test settings."""
    settings = get_settings()
    # Override settings for testing if needed
    return settings

# Mock database session
@pytest_asyncio.fixture
async def mock_db():
    """Create a mock database session."""
    mock = AsyncMock()
    # Add any specific mock behaviors needed
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.close = AsyncMock()
    
    yield mock

# Mock HTTP client session
@pytest_asyncio.fixture
async def mock_aiohttp_session():
    """Create a mock aiohttp ClientSession."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value='{"success": true}')
    mock_response.json = AsyncMock(return_value={"success": True})
    mock_response.__aenter__.return_value = mock_response
    
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.put = AsyncMock(return_value=mock_response)
    mock_session.delete = AsyncMock(return_value=mock_response)
    mock_session.request = AsyncMock(return_value=mock_response)
    mock_session.close = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    
    yield mock_session

# Sample test data
@pytest.fixture
def sample_listing_data():
    """Return sample listing data for tests."""
    return {
        "name": "Test Company",
        "symbol": "TEST",
        "listing_date": "2023-01-01T00:00:00",
        "lot_size": 100,
        "status": "New Listing",
        "exchange_code": "NASDAQ",
        "url": "https://example.com/test",
        "security_type": "Equity",
        "listing_detail_url": "https://example.com/test/details"
    }

@pytest.fixture
def sample_listings_data():
    """Return a list of sample listings for tests."""
    return [
        {
            "name": "Test Company 1",
            "symbol": "TEST1",
            "listing_date": "2023-01-01T00:00:00",
            "lot_size": 100,
            "status": "New Listing",
            "exchange_code": "NASDAQ",
            "url": "https://example.com/test1",
            "security_type": "Equity",
            "listing_detail_url": "https://example.com/test1/details"
        },
        {
            "name": "Test Company 2",
            "symbol": "TEST2",
            "listing_date": "2023-01-02T00:00:00",
            "lot_size": 200,
            "status": "New Listing",
            "exchange_code": "NYSE",
            "url": "https://example.com/test2",
            "security_type": "Equity",
            "listing_detail_url": "https://example.com/test2/details"
        }
    ]