from typing import List
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import asyncio

from backend.scraper_service.scrapers.base import BaseScraper
from backend.core.models import ListingBase, ScrapingResult
from backend.core.exceptions import ParsingError, ScraperError
from backend.core.utils import HKEXUtils

class HKEXScraper(BaseScraper):
    """Scraper for Hong Kong Stock Exchange new listings."""

    def __init__(self):
        super().__init__()
        self.url = "https://www.hkex.com.hk/Services/Trading/Securities/Trading-News/Newly-Listed-Securities?sc_lang=en"

    async def scrape(self) -> ScrapingResult:
        """Scrape HKEX for new listings."""
        try:
            self.logger.info(f"Starting HKEX scraping from URL: {self.url}")
            
            try:
                content = await self._make_request(
                    self.url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    },
                    timeout=60
                )
            except asyncio.TimeoutError:
                self.logger.warning("Timeout accessing HKEX website. Retrying with longer timeout.")
                content = await self._make_request(
                    self.url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    },
                    timeout=120
                )
            
            listings = self.parse(content)
            self.logger.info(f"Successfully parsed {len(listings)} listings from HKEX")
            
            return ScrapingResult(
                success=True,
                message=f"Successfully scraped {len(listings)} listings from HKEX",
                data=listings
            )
        except Exception as e:
            error_msg = f"Failed to scrape HKEX: {str(e)}"
            self.logger.error(error_msg)
            self.logger.debug(f"Detailed error: {str(e)}", exc_info=True)
            raise ScraperError(error_msg) from e

    def parse(self, content: str) -> List[ListingBase]:
        """Parse the HTML content and extract listings."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            table = soup.find('table', {'class': 'table migrate'})
            
            if not table:
                error_msg = "Could not find listings table in HKEX page"
                self.logger.error(error_msg)
                raise ParsingError(error_msg)

            listings = []
            rows = table.find_all('tr')[1:]  # Skip header
            self.logger.debug(f"Found {len(rows)} rows in the listings table")
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 10:
                    listing = self._parse_row(cols)
                    if listing:
                        listings.append(listing)
                else:
                    self.logger.warning(f"Skipping row with insufficient columns: {len(cols)}")

            self.logger.info(f"Successfully parsed {len(listings)} valid listings")
            return listings
        except Exception as e:
            error_msg = f"Failed to parse HKEX content: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ParsingError(error_msg) from e

    def _parse_row(self, cols) -> ListingBase:
        """Parse a row of listing data."""
        try:
            # Extract data from columns
            listing_date = datetime.strptime(cols[0].text.strip().rstrip('*'), '%d/%m/%Y')
            
            # Get name and URL from first link if present
            name_col = cols[1]
            name = name_col.text.strip()
            url = None
            link = name_col.find('a')
            if link and 'href' in link.attrs:
                url = link['href']
            
            # Get symbol from second column
            symbol = cols[2].text.strip()
            lot_size = int(cols[3].text.strip().replace(',', ''))
            status = cols[8].text.strip() or "New Listing"
            
            # Get listing detail URL and security type from HKEXUtils
            listing_detail_url, security_type = HKEXUtils.get_listing_detail_url(symbol, name, status)
            
            return ListingBase(
                name=name,
                symbol=symbol,
                listing_date=listing_date,
                lot_size=lot_size,
                status=status,
                exchange_code='HKEX',
                security_type=security_type,
                url=url,
                listing_detail_url=listing_detail_url
            )
        except Exception as e:
            self.logger.error(f"Failed to parse row: {str(e)}", exc_info=True)
            raise ParsingError(f"Failed to parse row: {str(e)}") from e

    async def get_filtered_listings(self, filter_type: str = 'all') -> pd.DataFrame:
        """Get listings with optional filtering."""
        try:
            content = await self._make_request(
                self.url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
                timeout=60
            )
            
            listings = self.parse(content)
            
            df = pd.DataFrame([vars(listing) for listing in listings])
            if df.empty:
                return df

            filters = {
                'new': df['status'] == 'New Listing',
                'rights': df['name'].str.contains('RTS', na=False),
                'all': slice(None)
            }
            return df[filters.get(filter_type, slice(None))].copy()
        except Exception as e:
            self.logger.error(f"Error in get_filtered_listings: {str(e)}")
            return pd.DataFrame()

    # Convenience methods
    async def get_new_listings(self) -> pd.DataFrame:
        """Get only new listings."""
        return await self.get_filtered_listings('new')

    async def get_rights_issues(self) -> pd.DataFrame:
        """Get only rights issues."""
        return await self.get_filtered_listings('rights') 