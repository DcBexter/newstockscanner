"""
Tests for the notification service.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.scraper_service.services.notification_service import CircuitBreaker, NotificationService


class AsyncContextManagerMock:
    """A custom async context manager for mocking responses."""

    def __init__(self, mock_response):
        self.mock_response = mock_response

    async def __aenter__(self):
        return self.mock_response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class AsyncContextManagerResponse:
    """Mock response that implements async context manager protocol."""

    def __init__(self, status=200, json_response=None, text_response=None):
        self.status = status
        self._json_response = json_response
        self._text_response = text_response
        self.json = AsyncMock(return_value=json_response)
        self.text = AsyncMock(return_value=text_response)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class AsyncContextManagerSession:
    """Mock session that implements async context manager protocol."""

    def __init__(self, mock_response):
        self.mock_response = mock_response
        self.post_call_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    def post(self, url, **kwargs):
        """Returns a context manager that tracks calls and returns the mock response."""
        self.post_call_count += 1
        return self.mock_response


class MockResponse:
    def __init__(self, status, json_response=None, text_response=None):
        self.status = status
        self._json_response = json_response
        self._text_response = text_response
        self.json_called = 0
        self.text_called = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def json(self):
        self.json_called += 1
        return self._json_response

    async def text(self):
        self.text_called += 1
        return self._text_response


class MockSession:
    def __init__(self, mock_response):
        self.mock_response = mock_response
        self.post_called = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def post(self, url, json=None):
        self.post_called += 1
        return self.mock_response


# Test the CircuitBreaker class
class TestCircuitBreaker:
    @staticmethod
    def test_initial_state():
        """Test that the circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failure_count == 0
        assert cb.allow_request() is True

    @staticmethod
    def test_record_failure():
        """Test that recording failures increments the counter."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failure_count == 1
        assert cb.allow_request() is True

    @staticmethod
    def test_open_circuit_after_threshold():
        """Test that the circuit opens after reaching the failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert cb.allow_request() is False

    @staticmethod
    def test_half_open_after_timeout(monkeypatch):
        """Test that the circuit transitions to HALF_OPEN after the timeout."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

        # Mock time.time() to control the timing
        current_time = 0
        monkeypatch.setattr("time.time", lambda: current_time)

        # Trigger circuit open
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert cb.allow_request() is False

        # Advance time past recovery timeout
        current_time += 11
        assert cb.allow_request() is True
        assert cb.state == CircuitBreaker.HALF_OPEN

    @staticmethod
    def test_reset_after_success_in_half_open():
        """Test that the circuit resets after successful calls in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=3, half_open_max_calls=2)

        # Set to HALF_OPEN state
        cb.state = CircuitBreaker.HALF_OPEN

        # Record successful calls
        cb.record_success()
        assert cb.state == CircuitBreaker.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failure_count == 0

    @staticmethod
    def test_back_to_open_after_failure_in_half_open():
        """Test that the circuit goes back to OPEN after failure in HALF_OPEN state."""
        cb = CircuitBreaker()
        cb.state = CircuitBreaker.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN


# Test the NotificationService class
@pytest.mark.asyncio
class TestNotificationService:
    @pytest.fixture
    def notification_service(self):
        """Create a notification service instance for testing."""
        return NotificationService(notification_url="http://test-notification-service:8001")

    @pytest.mark.asyncio
    async def test_send_listing_notifications_success(self, notification_service, sample_listings_data, monkeypatch):
        """Test successful notification sending."""
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"success": True, "message": "Notifications sent"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Create a mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Mock the ClientSession class
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await notification_service.send_listing_notifications(sample_listings_data)

            # Verify the result
            assert result is True

            # Verify the response was used correctly
            assert mock_response.json.await_count == 1
            assert mock_session.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_listing_notifications_empty(self, notification_service, monkeypatch):
        """Test handling of empty listings data."""
        result = await notification_service.send_listing_notifications([])
        assert result is True

    @pytest.mark.asyncio
    async def test_send_listing_notifications_server_error(self, notification_service, sample_listings_data, monkeypatch):
        """Test handling of server errors."""
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Create a mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Mock the fallback method
        notification_service._handle_fallback = AsyncMock(return_value=True)

        # Mock the ClientSession class
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await notification_service.send_listing_notifications(sample_listings_data)

            # Verify the result
            assert result is True

            # Verify the response was used correctly
            assert mock_response.text.await_count == 3  # Called once for each retry
            assert mock_session.post.call_count == 3  # Should retry 3 times
            # Should call fallback once
            assert notification_service._handle_fallback.await_count == 1

    @pytest.mark.asyncio
    async def test_log_to_file_fallback(self, notification_service, sample_listings_data, tmp_path, monkeypatch):
        """Test the file logging fallback mechanism."""
        # Set up a temporary directory for fallback logs
        fallback_dir = tmp_path / "fallback_notifications"
        monkeypatch.setenv("NOTIFICATION_FALLBACK_DIR", str(fallback_dir))

        # Call the fallback method
        result = await notification_service._log_to_file(sample_listings_data)

        # Verify the result
        assert result is True

        # Verify a file was created
        assert fallback_dir.exists()
        files = list(fallback_dir.glob("*.json"))
        assert len(files) == 1

        # Verify file contents
        with open(files[0], "r") as f:
            saved_data = json.load(f)
            assert len(saved_data) == 2
            assert saved_data[0]["symbol"] == "TEST1"
            assert saved_data[1]["symbol"] == "TEST2"

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, notification_service, sample_listings_data):
        """Test integration with circuit breaker."""
        # Mock the circuit breaker to be in OPEN state
        notification_service.circuit_breaker.state = CircuitBreaker.OPEN
        notification_service._handle_fallback = AsyncMock(return_value=True)

        result = await notification_service.send_listing_notifications(sample_listings_data)

        # Verify fallback was called due to open circuit
        notification_service._handle_fallback.assert_called_once_with(sample_listings_data)
        assert result is True
