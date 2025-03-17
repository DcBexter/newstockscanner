from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, Union
import aiohttp
import asyncio
from contextlib import suppress

from backend.config.settings import get_settings
from backend.core.exceptions import HTTPError
from backend.core.models import ScrapingResult
from backend.config.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class BaseScraper(ABC):
    """Base class for all scrapers with common HTTP functionality and lifecycle management."""

    def __init__(self):
        """Initialize the scraper with necessary components."""
        self._session: Optional[aiohttp.ClientSession] = None
        self.settings = settings
        self.logger = logger

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
        """
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
                    return await response.text()
                    
            except aiohttp.ClientError as e:
                self.logger.warning(
                    f"Request to {url} failed (attempt {attempt + 1}/{self.settings.MAX_RETRIES}): {str(e)}"
                )
                if attempt == self.settings.MAX_RETRIES - 1:
                    raise HTTPError(
                        getattr(e, 'status', 500),
                        f"Failed after {self.settings.MAX_RETRIES} attempts: {str(e)}"
                    )
                await asyncio.sleep(min(2 ** attempt, 30))  # Exponential backoff with maximum delay

    @abstractmethod
    async def scrape(self) -> ScrapingResult:
        """Implement the scraping logic in derived classes.
        
        Returns:
            ScrapingResult containing success status, message, and scraped data
        """
        pass

    @abstractmethod
    def parse(self, content: str) -> Any:
        """Implement the parsing logic in derived classes.
        
        Args:
            content: Raw content to parse
            
        Returns:
            Parsed data in the format required by the specific scraper
        """
        pass

    async def run_scraping_task(self) -> ScrapingResult:
        """Run the complete scraping process with error handling.
        
        Returns:
            ScrapingResult containing success status, message, and scraped data
        """
        try:
            async with self:
                result = await self.scrape()
                if result.success:
                    self.logger.info(f"Scraping completed successfully: {result.message}")
                else:
                    self.logger.warning(f"Scraping completed with issues: {result.message}")
                return result
        except Exception as e:
            error_msg = f"Scraping failed: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            self.logger.debug("Detailed error:", exc_info=True)
            return ScrapingResult(success=False, message=error_msg, data=[])
        finally:
            await self._close_session() 
