import asyncio
import hashlib
import json
import os
import time
import urllib.parse
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Optional, Any, Dict, List

import aiohttp

from backend.config.log_config import get_logger
from backend.config.settings import get_settings
from backend.core.exceptions import HTTPError, ScraperError, RateLimitError
from backend.core.models import ScrapingResult, ListingBase

settings = get_settings()
logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter for HTTP requests.

    This class implements a rate limiter that enforces a maximum number of requests
    per minute to each domain. It tracks the last request time for each domain and
    enforces a minimum delay between requests to the same domain.

    Attributes:
        requests_per_minute (int): Maximum number of requests per minute.
        domain_specific (bool): Whether to apply rate limiting per domain or globally.
        last_request_time (Dict[str, float]): Mapping of domains to last request times.
        request_counts (Dict[str, int]): Mapping of domains to request counts in the current minute.
        last_minute_start (Dict[str, float]): Mapping of domains to the start time of the current minute.
    """

    def __init__(self, requests_per_minute: int = 30, domain_specific: bool = True):
        """Initialize the rate limiter.

        Args:
            requests_per_minute (int, optional): Maximum number of requests per minute.
                Defaults to 30.
            domain_specific (bool, optional): Whether to apply rate limiting per domain
                or globally. Defaults to True.
        """
        self.requests_per_minute = requests_per_minute
        self.domain_specific = domain_specific
        self.last_request_time: Dict[str, float] = defaultdict(float)
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.last_minute_start: Dict[str, float] = defaultdict(float)

    def get_domain(self, url: str) -> str:
        """Extract the domain from a URL.

        Args:
            url (str): The URL to extract the domain from.

        Returns:
            str: The domain of the URL, or "global" if domain_specific is False.
        """
        if not self.domain_specific:
            return "global"

        try:
            parsed_url = urllib.parse.urlparse(url)
            return parsed_url.netloc
        except Exception:
            # Fall back to global rate limiting if URL parsing fails
            return "global"

    async def wait_if_needed(self, url: str) -> None:
        """Wait if necessary to comply with rate limits.

        This method checks if a request to the given URL would exceed the rate limit
        and waits if necessary to comply with the limit.

        Args:
            url (str): The URL to check.

        Raises:
            RateLimitError: If the rate limit would be exceeded even after waiting
                for a reasonable amount of time.
        """
        if not settings.RATE_LIMIT_ENABLED:
            return

        domain = self.get_domain(url)
        current_time = time.time()

        # Check if we're in a new minute
        if current_time - self.last_minute_start[domain] >= 60:
            self.last_minute_start[domain] = current_time
            self.request_counts[domain] = 0

        # Check if we've exceeded the rate limit
        if self.request_counts[domain] >= self.requests_per_minute:
            # Calculate time until the next minute starts
            time_until_reset = 60 - (current_time - self.last_minute_start[domain])

            # If the wait time is reasonable, wait
            if time_until_reset <= 30:  # Only wait up to 30 seconds
                logger.warning(f"Rate limit reached for {domain}. Waiting {time_until_reset:.1f}s")
                await asyncio.sleep(time_until_reset)

                # Reset for the new minute
                self.last_minute_start[domain] = time.time()
                self.request_counts[domain] = 0
            else:
                # If the wait time is too long, raise an error
                raise RateLimitError(
                    message=f"Rate limit exceeded for {domain}",
                    retry_after=int(time_until_reset),
                    url=url
                )

        # Calculate minimum delay between requests (ensures even distribution)
        min_delay = 60 / self.requests_per_minute
        time_since_last_request = current_time - self.last_request_time[domain]

        if time_since_last_request < min_delay:
            delay = min_delay - time_since_last_request
            logger.debug(f"Rate limiting: waiting {delay:.2f}s before requesting {domain}")
            await asyncio.sleep(delay)

        # Update tracking
        self.last_request_time[domain] = time.time()
        self.request_counts[domain] += 1


class CircuitBreaker:
    """Circuit breaker pattern implementation to prevent overwhelming failing services."""

    # Circuit breaker states
    CLOSED = 'closed'      # Normal operation, requests flow through
    OPEN = 'open'          # Service is failing, requests are blocked
    HALF_OPEN = 'half_open'  # Testing if service has recovered

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30, 
                 half_open_max_calls: int = 1):
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


class BaseScraper(ABC):
    """Base class for all scrapers with common HTTP functionality and lifecycle management."""

    def __init__(self):
        """Initialize the scraper with necessary components."""
        self._session: Optional[aiohttp.ClientSession] = None
        self.settings = settings
        self.logger = logger
        self.circuit_breaker = CircuitBreaker()
        self.rate_limiter = RateLimiter(
            requests_per_minute=self.settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
            domain_specific=self.settings.RATE_LIMIT_DOMAIN_SPECIFIC
        )
        self.fallback_enabled = self.settings.ENABLE_FALLBACK_SCRAPING if hasattr(self.settings, 'ENABLE_FALLBACK_SCRAPING') else True
        self.last_successful_data: List[ListingBase] = []
        self.last_successful_time: Optional[datetime] = None
        self.last_scrape_time: Dict[str, datetime] = {}

    async def __aenter__(self):
        """Enter async context: create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context: properly close HTTP session."""
        await self._close_session()

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get current HTTP session or raise error if not initialized."""
        if not self._session or self._session.closed:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")
        return self._session

    async def _close_session(self) -> None:
        """Close HTTP session safely."""
        if self._session and not self._session.closed:
            with suppress(Exception):
                await self._session.close()
            self._session = None

    def _get_cache_key(self, url: str) -> str:
        """Generate a cache key for a URL."""
        return hashlib.md5(url.encode()).hexdigest()

    async def _cache_response(self, url: str, content: str) -> None:
        """Cache a successful response."""
        try:
            cache_key = self._get_cache_key(url)
            cache_dir = getattr(self.settings, 'SCRAPER_CACHE_DIR', './scraper_cache')
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f"{cache_key}.json")

            cache_data = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "content": content
            }

            # Convert to JSON string first, then write to file to avoid type issues
            json_str = json.dumps(cache_data)
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(json_str)

            self.logger.debug(f"Cached response for {url}")
        except Exception as e:
            self.logger.warning(f"Failed to cache response: {str(e)}")

    async def _get_cached_response(self, url: str) -> Optional[str]:
        """Get a cached response if available and not too old."""
        try:
            cache_key = self._get_cache_key(url)
            cache_dir = getattr(self.settings, 'SCRAPER_CACHE_DIR', './scraper_cache')
            cache_file = os.path.join(cache_dir, f"{cache_key}.json")

            if not os.path.exists(cache_file):
                return None

            # Check if cache is too old (default: 24 hours)
            max_age = getattr(self.settings, 'SCRAPER_CACHE_MAX_AGE', 86400)  # 24 hours in seconds
            if os.path.getmtime(cache_file) + max_age < time.time():
                self.logger.debug(f"Cache for {url} is too old")
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            return cache_data.get("content")
        except Exception as e:
            self.logger.warning(f"Failed to get cached response: {str(e)}")
            return None

    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> str:
        """Make an HTTP request with retry logic and exponential backoff.

        Args:
            url: Target URL for the request
            method: HTTP method to use
            headers: Optional HTTP headers
            params: Optional query parameters
            data: Optional request body (as JSON)
            timeout: Optional request timeout in seconds

        Returns:
            String response content

        Raises:
            HTTPError: If the request fails after maximum retries
            ScraperError: For other scraper-specific errors
            RateLimitError: If the rate limit would be exceeded even after waiting
        """
        # Check circuit breaker first
        if not self.circuit_breaker.allow_request():
            raise ScraperError(
                "Circuit breaker is OPEN - target service appears to be down",
                status_code=503,
                url=url
            )

        # Apply rate limiting
        try:
            await self.rate_limiter.wait_if_needed(url)
        except RateLimitError as e:
            self.logger.warning(f"Rate limit exceeded for {url}: {str(e)}")
            raise

        default_headers = {"User-Agent": self.settings.USER_AGENT}
        if headers:
            default_headers.update(headers)

        timeout_obj = aiohttp.ClientTimeout(total=timeout or self.settings.REQUEST_TIMEOUT)

        for attempt in range(self.settings.MAX_RETRIES):
            try:
                async with self.session.request(
                    method=method,
                    url=url,
                    headers=default_headers,
                    params=params,
                    json=data,
                    timeout=timeout_obj
                ) as response:
                    response.raise_for_status()
                    content = await response.text()
                    self.circuit_breaker.record_success()
                    return content

            except aiohttp.ClientConnectorError as e:
                # Connection errors - service might be down
                error_msg = f"Connection error to {url}: {str(e)}"
                self.logger.error(error_msg)
                self.circuit_breaker.record_failure()

                if attempt < self.settings.MAX_RETRIES - 1:
                    # Use exponential backoff with jitter
                    delay = min(2 ** attempt + (attempt * 0.1), 30)
                    self.logger.warning(f"Retrying in {delay:.1f}s (Attempt {attempt + 1}/{self.settings.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    raise HTTPError(
                        status_code=503,  # Service Unavailable
                        message=f"Failed to connect to {url} after {self.settings.MAX_RETRIES} attempts: {str(e)}"
                    )

            except aiohttp.ServerDisconnectedError as e:
                # Server disconnected - might be restarting or overloaded
                error_msg = f"Server disconnected from {url}: {str(e)}"
                self.logger.error(error_msg)
                self.circuit_breaker.record_failure()

                if attempt < self.settings.MAX_RETRIES - 1:
                    # Use exponential backoff with longer delay for server issues
                    delay = min(2 ** (attempt + 1), 30)
                    self.logger.warning(f"Retrying in {delay:.1f}s (Attempt {attempt + 1}/{self.settings.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    raise HTTPError(
                        status_code=503,  # Service Unavailable
                        message=f"Server disconnected from {url} after {self.settings.MAX_RETRIES} attempts: {str(e)}"
                    )

            except aiohttp.ClientResponseError as e:
                # Response errors - might be temporary
                status = getattr(e, 'status', 500)
                error_msg = f"Response error from {url}: {status} - {str(e)}"
                self.logger.error(error_msg)

                if status >= 500:  # Server errors
                    self.circuit_breaker.record_failure()

                if status == 429:  # Too Many Requests
                    # Rate limiting - always retry with longer backoff
                    retry_after = getattr(e, 'headers', {}).get('Retry-After')
                    delay = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** (attempt + 2)
                    delay = min(delay, 60)  # Cap at 60 seconds
                    self.logger.warning(f"Rate limited by {url}. Retry after {delay}s")
                    await asyncio.sleep(delay)
                    continue

                if attempt < self.settings.MAX_RETRIES - 1 and status >= 500:
                    # Only retry server errors
                    delay = min(2 ** attempt, 30)
                    self.logger.warning(f"Retrying in {delay}s (Attempt {attempt + 1}/{self.settings.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    raise HTTPError(
                        status_code=status,
                        message=f"HTTP error from {url}: {status} - {str(e)}"
                    )

            except aiohttp.ClientError as e:
                # Other client errors
                self.logger.warning(
                    f"Request to {url} failed (attempt {attempt + 1}/{self.settings.MAX_RETRIES}): {str(e)}"
                )
                if attempt == self.settings.MAX_RETRIES - 1:
                    self.circuit_breaker.record_failure()
                    raise HTTPError(
                        status_code=getattr(e, 'status', 500),
                        message=f"Failed after {self.settings.MAX_RETRIES} attempts: {str(e)}"
                    )
                await asyncio.sleep(min(2 ** attempt, 30))  # Exponential backoff with maximum delay

            except asyncio.TimeoutError:
                # Timeout errors
                error_msg = f"Request to {url} timed out after {timeout or self.settings.REQUEST_TIMEOUT}s"
                self.logger.error(error_msg)

                if attempt < self.settings.MAX_RETRIES - 1:
                    # Use exponential backoff
                    delay = min(2 ** attempt, 30)
                    self.logger.warning(f"Retrying in {delay}s (Attempt {attempt + 1}/{self.settings.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    self.circuit_breaker.record_failure()
                    raise HTTPError(
                        status_code=408,  # Request Timeout
                        message=f"Request to {url} timed out after {self.settings.MAX_RETRIES} attempts"
                    )

            except Exception as e:
                # Unexpected errors
                error_msg = f"Unexpected error requesting {url}: {type(e).__name__}: {str(e)}"
                self.logger.error(error_msg)

                if attempt < self.settings.MAX_RETRIES - 1:
                    # Use exponential backoff
                    delay = min(2 ** attempt, 30)
                    self.logger.warning(f"Retrying in {delay}s (Attempt {attempt + 1}/{self.settings.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    self.circuit_breaker.record_failure()
                    raise ScraperError(
                        message=f"Unexpected error after {self.settings.MAX_RETRIES} attempts: {str(e)}",
                        status_code=500,
                        url=url
                    )

    @abstractmethod
    async def scrape(self) -> ScrapingResult:
        """Implement the scraping logic in derived classes.

        Returns:
            ScrapingResult containing success status, message, and scraped data
        """
        pass

    async def get_last_scrape_time(self, source_id: str) -> Optional[datetime]:
        """Get the last time this source was scraped.

        Args:
            source_id (str): Identifier for the data source (e.g., "nasdaq", "hkex")

        Returns:
            Optional[datetime]: The last time this source was scraped, or None if
                it has never been scraped before.
        """
        return self.last_scrape_time.get(source_id)

    def set_last_scrape_time(self, source_id: str, time: datetime = None) -> None:
        """Set the last time this source was scraped.

        Args:
            source_id (str): Identifier for the data source (e.g., "nasdaq", "hkex")
            time (datetime, optional): The time to set. Defaults to current time.
        """
        self.last_scrape_time[source_id] = time or datetime.now()

    def get_incremental_date_range(self, source_id: str) -> tuple[Optional[datetime], datetime]:
        """Get the date range for incremental scraping.

        This method calculates the date range for incremental scraping based on
        the last scrape time and the maximum days setting.

        Args:
            source_id (str): Identifier for the data source (e.g., "nasdaq", "hkex")

        Returns:
            tuple[Optional[datetime], datetime]: A tuple of (start_date, end_date)
                where start_date is the last scrape time or None if it has never
                been scraped before, and end_date is the current time.
        """
        if not self.settings.INCREMENTAL_SCRAPING_ENABLED:
            return None, datetime.now()

        last_scrape = self.get_last_scrape_time(source_id)

        # If never scraped before, or if it was scraped too long ago,
        # use the maximum days setting
        if last_scrape is None or (datetime.now() - last_scrape).days > self.settings.INCREMENTAL_SCRAPING_MAX_DAYS:
            start_date = datetime.now() - timedelta(days=self.settings.INCREMENTAL_SCRAPING_MAX_DAYS)
        else:
            start_date = last_scrape

        return start_date, datetime.now()

    @abstractmethod
    def parse(self, content: str) -> Any:
        """Implement the parsing logic in derived classes.

        Args:
            content: Raw content to parse

        Returns:
            Parsed data in the format required by the specific scraper
        """

    async def _handle_scraping_failure(self, error: Exception) -> ScrapingResult:
        """Handle scraping failures with appropriate fallback mechanisms.

        Args:
            error: The exception that caused the failure

        Returns:
            ScrapingResult with fallback data if available, or error information
        """
        error_type = type(error).__name__
        error_msg = f"Scraping failed: {error_type}: {str(error)}"
        self.logger.error(error_msg)
        self.logger.debug("Detailed error:", exc_info=True)

        # Check if we have cached data to use as fallback
        if self.fallback_enabled and self.last_successful_data:
            # Only use cached data if it's not too old (default: 24 hours)
            max_age_hours = getattr(self.settings, 'FALLBACK_MAX_AGE_HOURS', 24)
            if (self.last_successful_time and 
                (datetime.now() - self.last_successful_time).total_seconds() < max_age_hours * 3600):
                self.logger.warning(f"Using fallback data from previous successful run ({len(self.last_successful_data)} items)")
                return ScrapingResult(
                    success=True,  # Mark as success but with a warning
                    message=f"Used fallback data due to error: {error_msg}",
                    data=self.last_successful_data,
                    is_fallback=True
                )

        # No fallback data available
        return ScrapingResult(success=False, message=error_msg, data=[])

    async def run_scraping_task(self) -> ScrapingResult:
        """Run the complete scraping process with error handling and fallback mechanisms.

        Returns:
            ScrapingResult containing success status, message, and scraped data
        """
        try:
            # Use the scraper as a context manager to ensure proper resource cleanup
            async with self:
                # Check circuit breaker first
                if not self.circuit_breaker.allow_request():
                    self.logger.warning("Circuit breaker is OPEN - using fallback data if available")
                    return await self._handle_scraping_failure(
                        ScraperError("Circuit breaker is OPEN - target service appears to be down", status_code=503)
                    )

                # Run the actual scraping
                result = await self.scrape()

                # Record success or failure in circuit breaker
                if result.success:
                    self.circuit_breaker.record_success()
                    self.logger.info(f"Scraping completed successfully: {result.message}")

                    # Cache successful results for fallback
                    if result.data:
                        self.last_successful_data = result.data
                        self.last_successful_time = datetime.now()
                else:
                    self.circuit_breaker.record_failure()
                    self.logger.warning(f"Scraping completed with issues: {result.message}")

                    # If no data was returned but we have fallback data, use it
                    if not result.data and self.fallback_enabled and self.last_successful_data:
                        self.logger.warning("No data returned, using fallback data from previous successful run")
                        return ScrapingResult(
                            success=True,
                            message=f"Used fallback data due to issues: {result.message}",
                            data=self.last_successful_data,
                            is_fallback=True
                        )

                return result

        except Exception as e:
            # Handle any unexpected exceptions
            return await self._handle_scraping_failure(e)

        finally:
            # Ensure resources are properly cleaned up
            await self._close_session()
