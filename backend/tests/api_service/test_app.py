"""
Tests for the API service application.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api_service.app import app, lifespan
from backend.core.exceptions import StockScannerError
from backend.database.session import close_db


# Simple test function at module level to help pytest discover tests
def test_module_level():
    """Simple test to help pytest discover this module."""
    assert True

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)

def create_test_app() -> FastAPI:
    """Create a test app instance with the same configuration as the main app."""
    test_app = FastAPI(
        title="Stock Scanner API Test",
        description="Test instance of the Stock Scanner API",
        version="0.1.0",
        lifespan=lifespan,
    )
    return test_app

@pytest.fixture(scope="function")
async def cleanup_connections():
    """Fixture to ensure database connections are properly closed."""
    yield
    # Get the current event loop
    loop = asyncio.get_running_loop()

    try:
        # Close database connections
        await close_db()

        # Run pending tasks to allow connections to close
        tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Give a small window for cleanup
        await asyncio.sleep(0.1)

    except Exception as e:
        print(f"Warning: Error during database cleanup: {e}")
    finally:
        # Ensure we don't leave any pending tasks
        for task in asyncio.all_tasks(loop):
            if task is not asyncio.current_task() and not task.done():
                task.cancel()

@pytest.fixture(scope="function")
async def mock_db():
    """Fixture to provide a mock database session."""
    mock_session = AsyncMock(spec=AsyncSession)
    yield mock_session

class TestAPIService:
    def test_root_endpoint(self, test_client):
        """Test the root endpoint returns the expected response."""
        response = test_client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Stock Scanner API is running"}

    def test_health_check_endpoint(self, test_client, monkeypatch):
        """Test the health check endpoint with a mocked database."""
        # Mock the database dependency
        mock_db = AsyncMock()
        # Configure the execute method to return a successful result
        mock_result = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Create a mock dependency override
        async def override_get_db():
            yield mock_db

        # Apply the mock
        from backend.database.session import get_db
        app.dependency_overrides = {
            get_db: override_get_db
        }

        # Make the request
        response = test_client.get("/health")

        # Clean up the override
        app.dependency_overrides = {}

        # Verify the response
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["database"] == "connected"

    def test_exception_handling(self, test_client, monkeypatch):
        """Test that exceptions are properly handled by the API."""
        # Create a route that raises an exception for testing
        test_router = APIRouter()

        @test_router.get("/test-error")
        async def test_error():
            raise StockScannerError("Test error")

        # Add the test router to the app
        app.include_router(test_router)

        # Make the request
        response = test_client.get("/test-error")

        # Verify the response
        assert response.status_code == 400
        assert response.json()["error"] == "Test error"
        assert response.json()["type"] == "StockScannerError"

@pytest.mark.asyncio
class TestAPIServiceAsync:
    @pytest.mark.asyncio
    async def test_startup_event(self, monkeypatch, cleanup_connections):
        """Test the startup event initializes the application correctly."""
        # Mock the dependencies
        mock_init_db = AsyncMock()
        mock_setup_logging = MagicMock()
        mock_close_db = AsyncMock()

        # Apply the mocks
        monkeypatch.setattr('backend.database.session.init_db', mock_init_db)
        monkeypatch.setattr('backend.database.session.close_db', mock_close_db)
        monkeypatch.setattr('backend.config.log_config.setup_logging', mock_setup_logging)
        monkeypatch.setattr('backend.api_service.app.setup_logging', mock_setup_logging)
        monkeypatch.setattr('backend.api_service.app.init_db', mock_init_db)
        monkeypatch.setattr('backend.api_service.app.close_db', mock_close_db)

        # Create a test app
        test_app = create_test_app()

        # Get the lifespan context manager
        lifespan_cm = lifespan

        # Enter the lifespan context manager to trigger startup
        async with lifespan_cm(test_app):
            # Verify the dependencies were called
            mock_setup_logging.assert_called_once()
            assert mock_init_db.called, "init_db should be called during startup"
            await mock_init_db.wait()  # Wait for init_db to complete

        # Verify close_db was called during shutdown
        assert mock_close_db.called, "close_db should be called during shutdown"
        await mock_close_db.wait()  # Wait for close_db to complete

    @pytest.mark.asyncio
    async def test_shutdown_event(self, monkeypatch, cleanup_connections):
        """Test the shutdown event cleans up resources correctly."""
        # Mock the dependencies
        mock_close_db = AsyncMock()
        mock_init_db = AsyncMock()

        # Apply the mocks
        monkeypatch.setattr('backend.database.session.close_db', mock_close_db)
        monkeypatch.setattr('backend.database.session.init_db', mock_init_db)
        monkeypatch.setattr('backend.api_service.app.close_db', mock_close_db)
        monkeypatch.setattr('backend.api_service.app.init_db', mock_init_db)

        # Create a test app
        test_app = create_test_app()

        # Get the lifespan context manager
        lifespan_cm = lifespan

        # Enter and exit the lifespan context manager to trigger both startup and shutdown
        async with lifespan_cm(test_app):
            # Verify that close_db hasn't been called yet
            assert not mock_close_db.called, "close_db should not be called during startup"

        # After exiting the context, verify that close_db was called
        assert mock_close_db.called, "close_db should be called during shutdown"
        await mock_close_db.wait()  # Wait for close_db to complete
