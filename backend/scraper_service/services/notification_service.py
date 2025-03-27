"""Notification service for the scraper service."""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

import aiohttp
from aiohttp import ClientConnectorError, ClientResponseError, ServerDisconnectedError

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern implementation to prevent overwhelming failing services."""

    # Circuit breaker states
    CLOSED = "closed"  # Normal operation, requests flow through
    OPEN = "open"  # Service is failing, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service has recovered

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30, half_open_max_calls: int = 1):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0

    def record_success(self):
        """Record a successful call."""
        if self.state == self.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                # Service has recovered
                self.state = self.CLOSED
                self.failure_count = 0
                self.half_open_calls = 0
                logger.info("Circuit breaker reset to CLOSED state (service recovered)")

    def record_failure(self):
        """Record a failed call."""
        self.last_failure_time = time.time()

        if self.state == self.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                # Too many failures, open the circuit
                self.state = self.OPEN
                logger.warning(f"Circuit breaker switched to OPEN state after {self.failure_count} failures")
        elif self.state == self.HALF_OPEN:
            # Failed during testing, back to open
            self.state = self.OPEN
            logger.warning("Circuit breaker back to OPEN state (service still failing)")

    def allow_request(self) -> bool:
        """Check if a request should be allowed based on the current state."""
        if self.state == self.CLOSED:
            return True

        if self.state == self.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                # Try a test request
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit breaker switched to HALF_OPEN state (testing service)")
                return True
            return False

        if self.state == self.HALF_OPEN:
            # Only allow limited calls in half-open state
            return self.half_open_calls < self.half_open_max_calls

        return True  # Default to allowing requests


class NotificationService:
    """Service for sending notifications about new stock listings."""

    def __init__(self, notification_url=None):
        self.MAX_RETRIES = 3
        self.BASE_RETRY_DELAY = 5  # seconds
        self.MAX_RETRY_DELAY = 60  # maximum delay in seconds
        self.notification_service_url = notification_url or os.getenv("NOTIFICATION_SERVICE_URL", "http://notification_service:8001")
        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker()
        # Fallback notification methods (could be expanded)
        self.fallback_enabled = os.getenv("ENABLE_FALLBACK_NOTIFICATIONS", "true").lower() == "true"

    async def _log_to_file(self, listings: List[Dict[str, Any]]) -> bool:
        """Fallback method: Log notifications to a file when service is unavailable."""
        try:
            log_dir = os.getenv("NOTIFICATION_FALLBACK_DIR", "./fallback_notifications")
            os.makedirs(log_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{log_dir}/notification_fallback_{timestamp}.json"

            import json

            with open(filename, "w") as f:
                json.dump(listings, f, indent=2)

            logger.info(f"Fallback: Saved {len(listings)} notifications to {filename}")
            return True
        except Exception as e:
            logger.error(f"Fallback notification failed: {str(e)}")
            return False

    async def _handle_fallback(self, listings: List[Dict[str, Any]]) -> bool:
        """Handle fallback notification methods when primary method fails."""
        if not self.fallback_enabled:
            logger.warning("Fallback notifications disabled - notifications will be lost")
            return False

        logger.info("Attempting fallback notification method")
        return await self._log_to_file(listings)

    async def _handle_http_error(self, response: aiohttp.ClientResponse, attempt: int) -> Tuple[bool, bool]:
        """Handle HTTP error responses with appropriate recovery strategies.

        Returns:
            Tuple[bool, bool]: (should_retry, is_success)
        """
        error_text = await response.text()
        status = response.status

        # Log the error with appropriate severity
        if status >= 500:
            logger.error(f"Server error from notification service: HTTP {status} - {error_text}")
            should_retry = True
        elif status == 429:
            # Rate limiting - always retry with longer backoff
            retry_after = response.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else self.BASE_RETRY_DELAY * 2
            logger.warning(f"Rate limited by notification service. Retry after {delay}s")
            await asyncio.sleep(delay)
            should_retry = True
        elif status >= 400:
            # Client errors - might be fixable, might not
            if status in (400, 422):
                # Bad request or validation error - likely a problem with our data
                logger.error(f"Client error from notification service: HTTP {status} - {error_text}")
                should_retry = False  # Don't retry bad data
            else:
                # Other client errors - might be temporary
                logger.warning(f"Client error from notification service: HTTP {status} - {error_text}")
                should_retry = attempt < self.MAX_RETRIES - 1
        else:
            # Unexpected status code
            logger.warning(f"Unexpected status from notification service: HTTP {status} - {error_text}")
            should_retry = attempt < self.MAX_RETRIES - 1

        if should_retry and attempt < self.MAX_RETRIES - 1:
            # Calculate exponential backoff with jitter
            delay = min(self.BASE_RETRY_DELAY * (2**attempt) + (attempt * 0.1), self.MAX_RETRY_DELAY)
            logger.warning(f"Retrying in {delay:.1f}s (Attempt {attempt + 1}/{self.MAX_RETRIES})")
            await asyncio.sleep(delay)
            return True, False

        if not should_retry:
            logger.error("Not retrying notification request due to error type")
        else:
            logger.error("Max retries exceeded for notification request")

        return False, False

    async def send_listing_notifications(self, listings: List[Dict[str, Any]]) -> bool:
        """Send notifications by calling the notification service API with improved error handling."""
        if not listings:
            logger.info("No new listings to notify about")
            return True

        # Check circuit breaker first
        if not self.circuit_breaker.allow_request():
            logger.warning("Circuit breaker is OPEN - notification service appears to be down")
            return await self._handle_fallback(listings)

        # Make listings JSON serializable (convert datetime objects to strings)
        serializable_listings = []
        for listing in listings:
            serialized_listing = {}
            for key, value in listing.items():
                serialized_listing[key] = value.isoformat() if isinstance(value, datetime) else value
            serializable_listings.append(serialized_listing)

        api_url = f"{self.notification_service_url}/api/v1/notifications/listings"

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"Sending notifications for {len(serializable_listings)} listings")

                # Use a timeout to prevent hanging requests
                timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout

                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(api_url, json=serializable_listings) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"Notification service response: {result}")
                            self.circuit_breaker.record_success()
                            return True
                        else:
                            # Handle HTTP errors with specific strategies
                            should_retry, is_success = await self._handle_http_error(response, attempt)
                            if is_success:
                                self.circuit_breaker.record_success()
                                return True
                            if not should_retry:
                                self.circuit_breaker.record_failure()
                                break
                            continue

            except ClientConnectorError as e:
                # Connection errors - service might be down
                error_msg = f"Connection error to notification service: {str(e)}"
                logger.error(error_msg)
                self.circuit_breaker.record_failure()

                if attempt < self.MAX_RETRIES - 1:
                    # Use exponential backoff
                    delay = min(self.BASE_RETRY_DELAY * (2**attempt), self.MAX_RETRY_DELAY)
                    logger.warning(f"Retrying in {delay:.1f}s (Attempt {attempt + 1}/{self.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries exceeded - notification service appears to be down")
                    return await self._handle_fallback(listings)

            except ServerDisconnectedError as e:
                # Server disconnected - might be restarting or overloaded
                error_msg = f"Server disconnected: {str(e)}"
                logger.error(error_msg)
                self.circuit_breaker.record_failure()

                if attempt < self.MAX_RETRIES - 1:
                    # Use exponential backoff with longer delay for server issues
                    delay = min(self.BASE_RETRY_DELAY * (2 ** (attempt + 1)), self.MAX_RETRY_DELAY)
                    logger.warning(f"Retrying in {delay:.1f}s (Attempt {attempt + 1}/{self.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries exceeded after server disconnection")
                    return await self._handle_fallback(listings)

            except ClientResponseError as e:
                # Response errors - might be temporary
                error_msg = f"Response error: {e.status} - {str(e)}"
                logger.error(error_msg)

                if e.status >= 500:  # Server errors
                    self.circuit_breaker.record_failure()

                if attempt < self.MAX_RETRIES - 1:
                    # Use exponential backoff
                    delay = min(self.BASE_RETRY_DELAY * (2**attempt), self.MAX_RETRY_DELAY)
                    logger.warning(f"Retrying in {delay:.1f}s (Attempt {attempt + 1}/{self.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries exceeded for response error")
                    return await self._handle_fallback(listings)

            except Exception as e:
                # General exception handling for other errors
                error_msg = f"Error sending notifications via API: {str(e)}"
                logger.error(error_msg)

                if attempt < self.MAX_RETRIES - 1:
                    # Use exponential backoff
                    delay = min(self.BASE_RETRY_DELAY * (2**attempt), self.MAX_RETRY_DELAY)
                    logger.warning(f"Retrying in {delay:.1f}s (Attempt {attempt + 1}/{self.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Max retries exceeded. {error_msg}")
                    return await self._handle_fallback(listings)

        # If we get here, all retries failed
        logger.error("All notification attempts failed")
        return await self._handle_fallback(listings)
