import asyncio
import re
from typing import List, Optional

import pandas as pd
from bs4 import BeautifulSoup

from backend.core.exceptions import ParsingError
from backend.core.models import ListingBase, ScrapingResult
from backend.core.utils import DateUtils, HKEXUtils
from backend.scraper_service.scrapers.base import BaseScraper


class HKEXScraper(BaseScraper):
    """Scraper for Hong Kong Stock Exchange new listings."""

    def __init__(self):
        """Initialize the Hong Kong Stock Exchange scraper."""
        super().__init__()
        self.url = "https://www.hkex.com.hk/Services/Trading/Securities/Trading-News/Newly-Listed-Securities?sc_lang=en"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def scrape(self) -> ScrapingResult:
        """Scrape HKEX for new listings."""
        try:
            self.logger.info(f"Starting HKEX scraping from URL: {self.url}")

            content = await self._fetch_hkex_content()
            if not content:
                return ScrapingResult(success=False, message="Failed to retrieve content from HKEX", data=[])

            listings = self.parse(content)
            self._log_listings_found(listings)

            return ScrapingResult(success=True, message=f"Successfully scraped {len(listings)} listings from HKEX", data=listings)
        except Exception as e:
            error_msg = f"Failed to scrape HKEX: {str(e)}"
            self.logger.error(error_msg)
            self.logger.debug(f"Detailed error: {str(e)}", exc_info=True)
            return ScrapingResult(success=False, message=error_msg, data=[])

    async def _fetch_hkex_content(self) -> Optional[str]:
        """Fetch content from HKEX with retry mechanism."""
        try:
            return await self._make_request(self.url, headers=self.headers, timeout=60)
        except asyncio.TimeoutError:
            self.logger.warning("Timeout accessing HKEX website. Retrying with longer timeout.")
            try:
                return await self._make_request(self.url, headers=self.headers, timeout=120)
            except Exception as e:
                self.logger.error(f"Failed to retrieve HKEX content after retry: {str(e)}")
                return None
        except Exception as e:
            self.logger.error(f"Error fetching HKEX content: {str(e)}")
            return None

    def _log_listings_found(self, listings: List[ListingBase]) -> None:
        """Log information about found listings."""
        self.logger.info(f"Successfully parsed {len(listings)} listings from HKEX")
        for listing in listings:
            self.logger.debug(f"Found listing: {listing.name} ({listing.symbol}) - {listing.listing_date}")

    def parse(self, content: str) -> List[ListingBase]:
        """Parse the HTML content and extract listings."""
        try:
            soup = BeautifulSoup(content, "html.parser")
            table = soup.find("table", {"class": "table migrate"})

            if not table:
                error_msg = "Could not find listings table in HKEX page"
                self.logger.error(error_msg)
                raise ParsingError(error_msg)

            listings = []
            rows = table.find_all("tr")[1:]  # Skip header
            self.logger.debug(f"Found {len(rows)} rows in the listings table")

            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 10:  # Ensure row has enough columns
                    try:
                        listing = self._parse_row(cols)
                        if listing:
                            listings.append(listing)
                    except Exception as e:
                        self.logger.warning(f"Error parsing row: {str(e)}")
                else:
                    self.logger.warning(f"Skipping row with insufficient columns: {len(cols)}")

            self.logger.info(f"Successfully parsed {len(listings)} valid listings")
            return listings
        except Exception as e:
            error_msg = f"Failed to parse HKEX content: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ParsingError(error_msg) from e

    def _parse_row(self, cols) -> Optional[ListingBase]:
        """Parse a row of listing data."""
        try:
            # Extract data from columns
            date_text = cols[0].text.strip().rstrip("*")
            if not date_text:
                return None

            # Use DateUtils to parse the date with UK/HK format
            listing_date = DateUtils.parse_date_with_format(date_text, DateUtils.UK_FORMAT)

            # Get name and URL from first link if present
            name_col = cols[1]
            name = name_col.text.strip()
            if not name:
                return None

            url = None
            link = name_col.find("a")
            if link and "href" in link.attrs:
                url = link["href"]

            # Extract stock code
            symbol_col = cols[2]
            symbol = symbol_col.text.strip()
            if not symbol:
                # Generate placeholder symbol if not found
                symbol = f"HK-{self._generate_symbol(name)}"

            # Minimum lot size
            lot_size_col = cols[3]
            lot_size_text = lot_size_col.text.strip()
            # Default to 1000 if parsing fails
            lot_size = self._parse_lot_size(lot_size_text) or 1000

            # Determine if this is a rights issue or new listing
            issue_type_col = cols[4]
            issue_type = issue_type_col.text.strip()
            status = "Rights Issue" if "Rights" in issue_type else "New Listing"

            # Get listing detail URL and security type from HKEXUtils
            listing_detail_url, security_type = HKEXUtils.get_listing_detail_url(symbol, name, status)

            # Create listing object
            return ListingBase(
                name=name[:100],  # Truncate name if too long
                symbol=symbol[:20],  # Truncate symbol if too long
                listing_date=listing_date,
                lot_size=lot_size,
                status=status,
                exchange_code="HKEX",
                security_type=security_type,
                url=url,
                listing_detail_url=listing_detail_url,
            )
        except Exception as e:
            self.logger.warning(f"Error parsing listing row: {str(e)}")
            return None

    def _parse_lot_size(self, lot_size_text: str) -> int:
        """Parse lot size from text.

        Args:
            lot_size_text: String containing lot size (e.g. "1,000" or "500")

        Returns:
            Integer lot size or 1000 as default
        """
        try:
            # Remove commas and any non-numeric characters
            cleaned_text = re.sub(r"[^\d]", "", lot_size_text)
            if not cleaned_text:
                return 1000
            return int(cleaned_text)
        except (ValueError, TypeError):
            return 1000

    def _generate_symbol(self, company_name: str) -> str:
        """Generate a symbol from company name.

        Args:
            company_name: The name of the company

        Returns:
            A simple alphanumeric symbol derived from the name
        """
        if not company_name:
            return "UNKNOWN"

        # Take first 5 alphanumeric characters
        alphanumeric = re.sub(r"[^a-zA-Z0-9]", "", company_name)
        return alphanumeric[:5].upper() or "HKEX"

    async def get_filtered_listings(self, filter_type: str = "all") -> pd.DataFrame:
        """Get listings with optional filtering."""
        try:
            content = await self._fetch_hkex_content()
            if not content:
                return pd.DataFrame()

            listings = self.parse(content)
            if not listings:
                return pd.DataFrame()

            df = pd.DataFrame([vars(listing) for listing in listings])

            filters = {"all": slice(None), "new_listings": df["status"] == "New Listing", "rights_issues": df["status"] == "Rights Issue"}

            filter_slice = filters.get(filter_type, slice(None))
            return df[filter_slice].copy()
        except Exception as e:
            self.logger.error(f"Error in get_filtered_listings: {str(e)}")
            return pd.DataFrame()

    # Convenience methods
    async def get_new_listings(self) -> pd.DataFrame:
        """Get only new listings."""
        return await self.get_filtered_listings("new_listings")

    async def get_rights_issues(self) -> pd.DataFrame:
        """Get only rights issues."""
        return await self.get_filtered_listings("rights_issues")
