import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from bs4 import BeautifulSoup

from backend.core.exceptions import ParsingError
from backend.core.models import ListingBase, ScrapingResult
from backend.core.utils import DateUtils
from backend.scraper_service.scrapers.base import BaseScraper


class NasdaqScraper(BaseScraper):
    """Scraper for NASDAQ new listings and IPOs."""

    def __init__(self):
        """Initialize NASDAQ scraper with necessary URLs."""
        super().__init__()
        # Main URLs for data sources
        self.html_url = "https://www.nasdaq.com/market-activity/ipos"
        self.api_url = "https://api.nasdaq.com/api/ipo/calendar"
        # Base URL for date-specific API
        self.api_url_alt = "https://api.nasdaq.com/api/ipo/calendar?date="
        self.base_url = "https://www.nasdaq.com"

        # Common headers for API requests
        self.api_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        }

    async def scrape(self) -> ScrapingResult:
        """Scrape NASDAQ IPO listings using API endpoints with HTML fallback."""
        self.logger.info(f"Starting NASDAQ IPO scraping")

        try:
            # Try primary API endpoint first
            result = await self._try_primary_api()
            if result and result.success:
                return result

            # Try alternative API endpoint
            result = await self._try_alternative_api()
            if result and result.success:
                return result

            # Fallback to HTML scraping
            self.logger.warning("API extraction failed, falling back to HTML scraping")
            return await self._scrape_html()

        except Exception as e:
            # Log the error and return empty result
            error_msg = f"Failed to scrape NASDAQ: {type(e).__name__}"
            self.logger.error(error_msg)
            self.logger.debug(f"Detailed error: {str(e)}", exc_info=True)

            return ScrapingResult(
                success=False,
                message=f"Error scraping NASDAQ: {type(e).__name__}",
                data=[],
            )

    async def scrape_with_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> ScrapingResult:
        """Scrape NASDAQ IPO listings within a specific date range.

        This method modifies the API URL to include date parameters for incremental scraping.
        It helps reduce the load on the NASDAQ API by only requesting data for a specific
        date range instead of all available data.

        Args:
            start_date (datetime): The start date for the date range.
            end_date (datetime): The end date for the date range.

        Returns:
            ScrapingResult: The result of the scraping operation.
        """
        self.logger.info(
            f"Starting NASDAQ IPO incremental scraping from {start_date} to {end_date}"
        )

        try:
            # Format dates for API
            start_str = start_date.strftime("%Y-%m")
            end_str = end_date.strftime("%Y-%m")

            # If same month, just use one API call
            if start_str == end_str:
                api_url = f"https://api.nasdaq.com/api/ipo/calendar?date={start_str}"
                try:
                    self.logger.info(f"Trying API endpoint with date: {api_url}")
                    content = await self._make_request(
                        api_url, headers=self.api_headers, timeout=60
                    )

                    self.logger.debug(
                        "Successfully retrieved data from NASDAQ API endpoint"
                    )
                    listings = self.parse_api_data(content)

                    if listings:
                        self._log_listings_found(listings, "date-specific API")
                        return ScrapingResult(
                            success=True,
                            message=f"Successfully scraped {len(listings)} listings from NASDAQ using date API",
                            data=listings,
                        )
                except (asyncio.TimeoutError, Exception) as e:
                    self.logger.warning(
                        f"Failed to fetch from date-specific NASDAQ API: {type(e).__name__}"
                    )
                    return await self._scrape_html()

            # Make a direct API call with the start date parameter first
            api_url = f"https://api.nasdaq.com/api/ipo/calendar?date={start_str}"
            try:
                self.logger.info(f"Trying API endpoint with date: {api_url}")
                content = await self._make_request(
                    api_url, headers=self.api_headers, timeout=60
                )

                self.logger.debug(
                    f"Successfully retrieved data from NASDAQ API endpoint for {start_str}"
                )
                listings = self.parse_api_data(content)

                if listings:
                    self._log_listings_found(
                        listings, f"date-specific API for {start_str}"
                    )
                    return ScrapingResult(
                        success=True,
                        message=f"Successfully scraped {len(listings)} listings from NASDAQ using date API",
                        data=listings,
                    )
            except (asyncio.TimeoutError, Exception) as e:
                self.logger.warning(
                    f"Failed to fetch from date-specific NASDAQ API for {start_str}: {type(e).__name__}"
                )
                # Continue to try other months if this fails

            # If we get here, the start date API call failed or returned no listings
            # Fall back to HTML scraping
            self.logger.warning("No data found with API scraping, falling back to HTML")
            return await self._scrape_html()

        except Exception as e:
            error_msg = f"Failed to scrape NASDAQ incrementally: {type(e).__name__}"
            self.logger.error(error_msg)
            self.logger.debug(f"Detailed error: {str(e)}", exc_info=True)

            # Fall back to regular scraping
            self.logger.info("Falling back to regular scraping")
            return await self.scrape()

    async def _try_primary_api(self) -> Optional[ScrapingResult]:
        """Try to fetch data from the primary API endpoint."""
        try:
            self.logger.info(f"Trying primary NASDAQ API endpoint: {self.api_url}")
            content = await self._make_request(
                self.api_url, headers=self.api_headers, timeout=60
            )

            self.logger.debug("Successfully retrieved NASDAQ IPO API data")
            listings = self.parse_api_data(content)

            if listings:
                self._log_listings_found(listings, "primary API")
                return ScrapingResult(
                    success=True,
                    message=f"Successfully scraped {len(listings)} listings from NASDAQ API",
                    data=listings,
                )
        except (asyncio.TimeoutError, Exception) as e:
            self.logger.warning(
                f"Failed to fetch from primary NASDAQ API: {type(e).__name__}"
            )

        return None

    async def _try_alternative_api(self) -> Optional[ScrapingResult]:
        """Try to fetch data from the alternative API endpoint."""
        try:
            self.logger.info(f"Trying alternative API endpoint: {self.api_url_alt}")
            content = await self._make_request(
                self.api_url_alt, headers=self.api_headers, timeout=60
            )

            self.logger.debug(
                "Successfully retrieved data from alternative NASDAQ API endpoint"
            )
            listings = self.parse_api_data(content)

            if listings:
                self._log_listings_found(listings, "alternative API")
                return ScrapingResult(
                    success=True,
                    message=f"Successfully scraped {len(listings)} listings from NASDAQ using alt API",
                    data=listings,
                )
        except (asyncio.TimeoutError, Exception) as e:
            self.logger.warning(
                f"Failed to fetch from alternative NASDAQ API: {type(e).__name__}"
            )

        return None

    async def _scrape_html(self) -> ScrapingResult:
        """Scrape NASDAQ IPO data from HTML as a fallback method."""
        try:
            content = await self._make_request(
                self.html_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
                timeout=60,
            )

            self.logger.debug("Successfully retrieved NASDAQ IPO HTML page")
            listings = self.parse(content)

            if listings:
                self._log_listings_found(listings, "HTML")
                return ScrapingResult(
                    success=True,
                    message=f"Successfully scraped {len(listings)} listings from NASDAQ HTML",
                    data=listings,
                )
            else:
                return ScrapingResult(
                    success=False, message="No listings found in NASDAQ HTML", data=[]
                )
        except Exception as html_err:
            self.logger.error(
                f"HTML scraping fallback also failed: {type(html_err).__name__}"
            )
            return ScrapingResult(
                success=False,
                message=f"Error scraping NASDAQ: All scraping methods failed",
                data=[],
            )

    def _log_listings_found(self, listings: List[ListingBase], source: str) -> None:
        """Log information about found listings."""
        self.logger.info(
            f"Successfully parsed {len(listings)} IPO listings from {source}"
        )
        for listing in listings:
            self.logger.debug(
                f"Found listing: {listing.name} ({listing.symbol}) - {listing.listing_date}"
            )

    def parse_api_data(self, content: str) -> List[ListingBase]:
        """Parse the API JSON data to extract IPO listings."""
        try:
            data = json.loads(content)
            listings = []

            # Check if data structure is present
            if not data.get("data"):
                self.logger.warning("API response missing 'data' field")
                return []

            # Process each section of the API response
            api_sections = {
                "priced": "Trading",
                "upcoming": "Upcoming IPO",
                "filings": "Filed IPO",
            }

            for section_name, status in api_sections.items():
                section_data = data["data"].get(section_name, {})
                if not section_data or not section_data.get("rows"):
                    self.logger.debug(f"No data in '{section_name}' section")
                    continue

                self.logger.debug(
                    f"Found {len(section_data['rows'])} rows in '{section_name}' section"
                )
                for row in section_data["rows"]:
                    try:
                        listing = self._create_listing_from_api_row(row, status)
                        if listing:
                            listings.append(listing)
                    except Exception as e:
                        self.logger.warning(
                            f"Error processing {section_name} row: {type(e).__name__}"
                        )

            return listings

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON data: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error in parse_api_data: {str(e)}")
            return []

    def _create_listing_from_api_row(
        self, row: Dict[str, Any], status: str = "Upcoming IPO"
    ) -> Optional[ListingBase]:
        """Create a ListingBase object from an API row."""
        try:
            # Extract company name
            name = row.get("companyName", "").strip()
            if not name:
                return None

            # Extract or generate symbol
            symbol = row.get("proposedTickerSymbol", "").strip()
            if not symbol:
                symbol = f"TBA-{name[:5] if len(name) >= 5 else name}"

            # Ensure symbol length is valid
            symbol = symbol[:20]

            # Parse listing date
            listing_date = self._parse_date_from_row(row)

            # Determine exchange
            exchange_code = self._determine_exchange_from_row(row)

            # Get lot size
            lot_size = self._parse_lot_size_from_row(row)

            # Determine status
            listing_status = status
            if status == "Trading" or row.get("offerPrice", ""):
                listing_status = "Trading"

            # Limit name length
            name = name[:100]

            return ListingBase(
                name=name,
                symbol=symbol,
                listing_date=listing_date,
                lot_size=lot_size,
                status=listing_status,
                exchange_code=exchange_code,
                security_type="Equity",
                url=f"https://www.nasdaq.com/market-activity/stocks/{symbol.lower()}"
                if symbol
                else None,
                listing_detail_url=None,
            )

        except Exception as e:
            self.logger.warning(f"Error creating listing: {type(e).__name__}")
            self.logger.debug(f"Error details: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _parse_date_from_row(row: Dict[str, Any]) -> datetime:
        """Parse the listing date from a row or use default date."""
        date_str = row.get("pricingDate", "") or row.get("expectedPriceDate", "")

        # Use DateUtils to parse the date string with a default of 30 days from now
        return DateUtils.parse_date(date_str, datetime.now() + timedelta(days=30))

    @staticmethod
    def _determine_exchange_from_row(row: Dict[str, Any]) -> str:
        """Determine exchange code from row data."""
        exchange_text = row.get("exchange", "") or row.get("proposedExchange", "")
        exchange_text = exchange_text.strip().upper()

        if "NASDAQ" in exchange_text:
            return "NASDAQ"
        elif "NYSE" in exchange_text:
            return "NYSE"
        else:
            return "NASDAQ"  # Default

    @staticmethod
    def _parse_lot_size_from_row(row: Dict[str, Any]) -> int:
        """Parse lot size from shares offered or use default."""
        shares_text = row.get("sharesOffered", "1000").strip()

        try:
            # Extract numeric part and convert to integer
            if not re.search(r"\d", shares_text):
                return 1000

            lot_size = int(re.sub(r"[^\d]", "", shares_text))
            return max(lot_size, 1000)  # Ensure minimum lot size
        except Exception:
            return 1000

    def parse(self, content: str) -> List[ListingBase]:
        """Parse the HTML content and extract IPO listings."""
        try:
            self.logger.debug("Starting to parse NASDAQ IPO page content")
            soup = BeautifulSoup(content, "html.parser")

            # First try parsing from tables
            listings = self._parse_tables(soup)

            # If no tables found, try parsing from script tags
            if not listings:
                self.logger.warning("No tables found in the HTML content")
                listings = self._parse_script_tags(soup)

            return listings

        except Exception as e:
            error_msg = f"Failed to parse NASDAQ content: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ParsingError(error_msg) from e

    def _parse_tables(self, soup: BeautifulSoup) -> List[ListingBase]:
        """Parse IPO data from HTML tables."""
        listings = []
        tables = soup.find_all("table")

        if not tables:
            return []

        self.logger.debug(f"Found {len(tables)} tables in the HTML")

        for table in tables:
            try:
                # Check if this table looks like an IPO table
                headers = table.find_all("th")
                header_text = " ".join([h.text.strip() for h in headers])

                if (
                    "Symbol" not in header_text
                    and "Company" not in header_text
                    and "Date" not in header_text
                ):
                    continue

                self.logger.debug("Found potential IPO table")
                rows = table.find_all("tr")[1:]  # Skip header
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 3:  # Need at least company, symbol, date
                        continue

                    # Extract data from table row
                    listing = self._create_listing_from_html_row(cols)
                    if listing:
                        listings.append(listing)
            except Exception as e:
                self.logger.warning(f"Error processing table: {str(e)}")

        return listings

    def _create_listing_from_html_row(self, cols) -> Optional[ListingBase]:
        """Create a listing from HTML table row columns."""
        try:
            name = cols[0].text.strip() if cols[0].text else "Unknown"
            symbol = cols[1].text.strip() if len(cols) > 1 and cols[1].text else ""

            if not symbol:
                symbol = f"TBA-{name[:5]}"

            # Find date column and parse date
            listing_date = self._extract_date_from_html_cols(cols)

            return ListingBase(
                name=name[:100],
                symbol=symbol[:20],
                listing_date=listing_date,
                lot_size=1000,  # Default
                status="Upcoming IPO",
                exchange_code="NASDAQ",  # Default
                security_type="Equity",
                url=None,
                listing_detail_url=None,
            )
        except Exception as e:
            self.logger.warning(f"Error creating listing from HTML row: {str(e)}")
            return None

    @staticmethod
    def _extract_date_from_html_cols(cols) -> datetime:
        """Extract date from HTML table columns."""
        default_date = datetime.now() + timedelta(days=30)

        for i, col in enumerate(cols):
            text = col.text.strip()
            if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", text):
                match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", text)
                if match:
                    # Use DateUtils to extract and parse the date
                    return DateUtils.parse_date(match.group(1), default_date)

        # Default if no date found
        return default_date

    def _parse_script_tags(self, soup: BeautifulSoup) -> List[ListingBase]:
        """Parse IPO data from script tags in HTML."""
        listings = []
        scripts = soup.find_all("script")

        for script in scripts:
            script_text = script.string
            if not script_text or "priceDate" not in script_text:
                continue

            self.logger.debug("Found IPO data in script tag")
            try:
                # Extract JSON data from script
                match = re.search(r"(\[{.*}])", script_text)
                if not match:
                    continue

                json_data = match.group(1)
                data = json.loads(json_data)

                for item in data:
                    try:
                        listing = self._create_listing_from_script_item(item)
                        if listing:
                            listings.append(listing)
                    except Exception as e:
                        self.logger.warning(
                            f"Error processing script data item: {str(e)}"
                        )
            except Exception as e:
                self.logger.warning(f"Error extracting data from script: {str(e)}")

        return listings

    def _create_listing_from_script_item(
        self, item: Dict[str, Any]
    ) -> Optional[ListingBase]:
        """Create a listing from a script tag JSON item."""
        try:
            name = item.get("companyName", "")
            if not name:
                return None

            symbol = item.get("symbol", "")
            if not symbol:
                symbol = f"TBA-{name[:5] if name else 'Unknown'}"

            # Parse date using DateUtils
            date_str = item.get("priceDate", "")
            default_date = datetime.now() + timedelta(days=30)
            listing_date = DateUtils.parse_date(date_str, default_date)

            # Determine exchange
            exchange_code = "NASDAQ"  # Default
            if item.get("exchange"):
                if "NYSE" in item.get("exchange", "").upper():
                    exchange_code = "NYSE"

            return ListingBase(
                name=name[:100],
                symbol=symbol[:20],
                listing_date=listing_date,
                lot_size=1000,  # Default
                status="Trading" if item.get("priceRange") else "Upcoming IPO",
                exchange_code=exchange_code,
                security_type="Equity",
                url=None,
                listing_detail_url=None,
            )
        except Exception as e:
            self.logger.warning(f"Error creating listing from script item: {str(e)}")
            return None

    async def get_filtered_listings(self, filter_type: str = "all") -> pd.DataFrame:
        """Get listings with optional filtering."""
        try:
            content = await self._make_request(
                self.api_url, headers=self.api_headers, timeout=60
            )

            listings = self.parse_api_data(content)

            if not listings:
                return pd.DataFrame()

            df = pd.DataFrame([vars(listing) for listing in listings])

            filters = {
                "upcoming": df["status"] == "Upcoming IPO",
                "priced": df["status"] == "Trading",
                "nasdaq_only": df["exchange_code"] == "NASDAQ",
                "nyse_only": df["exchange_code"] == "NYSE",
                "all": slice(None),
            }

            filter_slice = filters.get(filter_type, slice(None))
            return df[filter_slice].copy()
        except Exception as e:
            self.logger.error(f"Error in get_filtered_listings: {str(e)}")
            return pd.DataFrame()

    # Convenience methods
    async def get_upcoming_ipos(self) -> pd.DataFrame:
        """Get only upcoming IPOs."""
        return await self.get_filtered_listings("upcoming")

    async def get_priced_ipos(self) -> pd.DataFrame:
        """Get only priced IPOs."""
        return await self.get_filtered_listings("priced")

    async def get_nasdaq_listings(self) -> pd.DataFrame:
        """Get only NASDAQ listings."""
        return await self.get_filtered_listings("nasdaq_only")

    async def get_nyse_listings(self) -> pd.DataFrame:
        """Get only NYSE listings."""
        return await self.get_filtered_listings("nyse_only")
