from abc import ABC, abstractmethod
from typing import Optional, Any, Dict
import aiohttp
import asyncio
from datetime import datetime

from backend.config.settings import get_settings
from backend.core.exceptions import HTTPError, ScraperError
from backend.core.models import ScrapingResult
from backend.config.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

class BaseScraper(ABC):
    """Base class for all scrapers."""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self.settings = settings
        self.logger = logger

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            try:
                await self._session.close()
                self._session = None
            except Exception as e:
                self.logger.error(f"Error closing client session: {str(e)}")
                # Don't re-raise to ensure the session closure attempt doesn't fail the whole operation

    @property
    def session(self) -> aiohttp.ClientSession:
        if not self._session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")
        return self._session

    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> str:
        """Make an HTTP request with retry logic."""
        
        default_headers = {
            "User-Agent": self.settings.USER_AGENT
        }
        if headers:
            default_headers.update(headers)

        timeout = timeout or self.settings.REQUEST_TIMEOUT
        
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                async with self.session.request(
                    method=method,
                    url=url,
                    headers=default_headers,
                    params=params,
                    json=data,
                    timeout=timeout
                ) as response:
                    response.raise_for_status()
                    return await response.text()
                    
            except aiohttp.ClientError as e:
                self.logger.error(f"Request failed (attempt {attempt + 1}/{self.settings.MAX_RETRIES}): {str(e)}")
                if attempt == self.settings.MAX_RETRIES - 1:
                    raise HTTPError(
                        getattr(e, 'status', 500),
                        f"Failed after {self.settings.MAX_RETRIES} attempts: {str(e)}"
                    )
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    @abstractmethod
    async def scrape(self) -> ScrapingResult:
        """Implement the scraping logic in derived classes.
        
        This method should handle the actual data collection process.
        Returns:
            ScrapingResult: Result object containing status and scraped data.
        """
        pass

    @abstractmethod
    def parse(self, content: str) -> Any:
        """Implement the parsing logic in derived classes.
        
        This method should transform raw content into structured data.
        Args:
            content: Raw content to parse (usually HTML or JSON)
        Returns:
            Parsed data in the appropriate format for the scraper
        """
        pass

    async def run_scraping_task(self) -> ScrapingResult:
        """Run the complete scraping process with error handling.
        
        This method orchestrates the entire scraping workflow:
        1. Initialize the session
        2. Call the scrape method
        3. Handle any errors
        4. Clean up resources
        
        Returns:
            ScrapingResult: Complete result of the scraping operation
        """
        result = None
        try:
            async with self:
                result = await self.scrape()
                if result.success:
                    self.logger.info(f"Scraping completed successfully: {result.message}")
                else:
                    self.logger.warning(f"Scraping completed with issues: {result.message}")
                return result
        except Exception as e:
            # Log only the exception type and message, not the full stack trace
            error_msg = f"Scraping failed: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            # Only log the full stack trace at debug level
            self.logger.debug("Detailed error:", exc_info=True)
            
            return ScrapingResult(
                success=False,
                message=error_msg,
                data=[]
            )
        finally:
            # Additional safety check to ensure session is closed
            if hasattr(self, '_session') and self._session is not None:
                try:
                    await self._session.close()
                    self._session = None
                    self.logger.debug("Session closed in run_scraping_task finally block")
                except Exception as close_err:
                    self.logger.error(f"Error closing session in finally block: {str(close_err)}") 
