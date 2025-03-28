import re
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from backend.core.exceptions import ParsingError
from backend.core.models import ListingBase, ScrapingResult
from backend.core.utils import DateUtils
from backend.scraper_service.scrapers.base import BaseScraper


class FrankfurtScraper(BaseScraper):
    """Scraper for Frankfurt Stock Exchange (Börse Frankfurt) listings."""

    def __init__(self):
        """Initialize Frankfurt Stock Exchange scraper."""
        super().__init__()
        # Base URL for Deutsche Börse Cash Market
        self.base_url = "https://www.deutsche-boerse-cash-market.com"

        # Frankfurt Stock Exchange announcements (the only reliable source for new listings)
        self.announcements_url = f"{self.base_url}/dbcm-de/newsroom/fwb-bekanntmachungen/fwb-bekanntmachungen-ii"

        # German headers for better results with the German page
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml",
        }

    async def scrape(self) -> ScrapingResult:
        """Scrape Frankfurt Stock Exchange new listings."""
        try:
            self.logger.info("Starting Frankfurt Stock Exchange scraping")

            # Get announcements that might contain listings
            self.logger.info(f"Scraping announcements: {self.announcements_url}")
            announcements_content = await self._make_request(self.announcements_url, headers=self.headers, timeout=60)

            # Parse the announcements
            listings = self.parse(announcements_content)

            if listings:
                self._log_listings_found(listings)
                return ScrapingResult(
                    success=True, message=f"Successfully scraped {len(listings)} listings from Frankfurt Stock Exchange", data=listings
                )
            else:
                return ScrapingResult(success=True, message="No new listings found from Frankfurt Stock Exchange", data=[])

        except Exception as e:
            error_msg = f"Failed to scrape Frankfurt Stock Exchange: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            self.logger.debug("Detailed error:", exc_info=True)
            return ScrapingResult(success=False, message=error_msg, data=[])

    def _log_listings_found(self, listings: List[ListingBase]) -> None:
        """Log information about found listings."""
        self.logger.info(f"Successfully parsed {len(listings)} new listings from Frankfurt Stock Exchange")
        for listing in listings:
            self.logger.debug(f"Found listing: {listing.name} ({listing.symbol}) - {listing.listing_date}")

    def parse(self, content: str) -> List[ListingBase]:
        """Parse the announcements page for new listings."""
        try:
            soup = BeautifulSoup(content, "html.parser")
            listings = []

            # Based on the actual HTML structure
            announcements = soup.select("ol.list.search-results > li")
            self.logger.info(f"Found {len(announcements)} announcements in the exact selector")

            # Process each announcement
            for announcement in announcements:
                try:
                    # Check if announcement is relevant for new listings
                    if not self._is_listing_announcement(announcement):
                        continue

                    # If relevant, extract the listing data
                    listing = self._process_announcement(announcement)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    self.logger.warning(f"Error processing announcement: {str(e)}")

            return listings

        except Exception as e:
            error_msg = f"Failed to parse Frankfurt Stock Exchange content: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ParsingError(error_msg) from e

    @staticmethod
    def _is_listing_announcement(announcement_elem) -> bool:
        """Check if an announcement is about a new listing."""
        with suppress(Exception):
            title_elem = announcement_elem.select_one(".contentCol > h3 > a")
            if not title_elem:
                return False

            title = title_elem.get_text(strip=True)

            # Check for new listing keywords in German
            listing_keywords = ["Neuemission", "Notierungsaufnahme", "Erstnotiz", "Zulassung", "Handel"]

            # Check if any of the listing keywords appear in the title
            return any(keyword.lower() in title.lower() for keyword in listing_keywords)

        return False

    def _process_announcement(self, announcement_elem) -> Optional[ListingBase]:
        """Extract listing data from an announcement element."""
        try:
            # Extract announcement title and URL
            title_elem = announcement_elem.select_one(".contentCol > h3 > a")
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            detail_url = None

            if "href" in title_elem.attrs:
                relative_url = title_elem.attrs["href"]
                detail_url = f"{self.base_url}{relative_url}" if relative_url.startswith("/") else relative_url

            # Extract date
            listing_date = self._extract_date(announcement_elem)

            # Extract company name and symbol from title
            name, symbol = self._extract_name_and_symbol(title)

            if not name:
                return None

            return ListingBase(
                name=name[:100],  # Truncate name if too long
                symbol=symbol[:20] if symbol else f"FSE-{name[:5]}",  # Use placeholder if no symbol found
                listing_date=listing_date,
                lot_size=1,  # Default for Frankfurt
                status="New Listing",
                exchange_code="FSE",  # Frankfurt Stock Exchange
                security_type="Equity",
                url=None,
                listing_detail_url=detail_url,
            )
        except Exception as e:
            self.logger.warning(f"Error processing announcement data: {str(e)}")
            return None

    @staticmethod
    def _extract_date(announcement_elem) -> datetime:
        """Extract and parse date from announcement element."""
        default_date = datetime.now() + timedelta(days=7)

        try:
            date_elem = announcement_elem.select_one(".indexCol > .date")
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                # Use DateUtils to parse the date with German format (DD.MM.YYYY)
                return DateUtils.parse_date_with_format(date_text, DateUtils.GERMAN_FORMAT, default_date)

            # If date element not found, return default date
            return default_date
        except Exception:
            # Default to a week from now if parsing fails
            return default_date

    @staticmethod
    def _extract_name_and_symbol(title: str) -> tuple:
        """Extract company name and trading symbol from announcement title."""
        name = ""
        symbol = ""

        # Common patterns for security names and symbols in German announcements
        # Example: "Neuemission: ABC AG (DE000A1234Z7)"

        # First try to extract by ISIN pattern (more reliable)
        isin_match = re.search(r"([A-Z0-9\s]+)\s*\(([A-Z]{2}[0-9A-Z]{10})\)", title)
        if isin_match:
            name = isin_match.group(1).strip()
            symbol = isin_match.group(2).strip()  # This is actually the ISIN
            return name, symbol

        # Try various patterns for company extraction
        colon_match = re.search(r":\s*([^(]+)", title)
        if colon_match:
            name = colon_match.group(1).strip()
            return name, symbol

        # If no patterns match, use the whole title as name
        if not name:
            # Remove common prefixes that aren't part of the company name
            prefixes = ["Neuemission:", "Notierungsaufnahme:", "Erstnotiz:", "Zulassung:", "Handel:"]
            cleaned_title = title
            for prefix in prefixes:
                cleaned_title = cleaned_title.replace(prefix, "").strip()
            name = cleaned_title

        return name, symbol

    async def get_latest_announcements(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the latest announcements from Frankfurt Stock Exchange."""
        try:
            content = await self._make_request(self.announcements_url, headers=self.headers, timeout=60)

            soup = BeautifulSoup(content, "html.parser")
            announcements = soup.select("ol.list.search-results > li")

            result = []
            for i, announcement in enumerate(announcements):
                if i >= limit:
                    break

                with suppress(Exception):
                    title_elem = announcement.select_one(".contentCol > h3 > a")
                    date_elem = announcement.select_one(".indexCol > .date")

                    title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                    date_text = date_elem.get_text(strip=True) if date_elem else "Unknown"

                    url = None
                    if title_elem and "href" in title_elem.attrs:
                        relative_url = title_elem.attrs["href"]
                        url = f"{self.base_url}{relative_url}" if relative_url.startswith("/") else relative_url

                    result.append({"title": title, "date": date_text, "url": url})

            return result
        except Exception as e:
            self.logger.error(f"Failed to get latest announcements: {str(e)}")
            return []
