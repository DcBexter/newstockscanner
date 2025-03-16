from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import pandas as pd
import logging
import json
import asyncio

from backend.scraper_service.scrapers.base import BaseScraper
from backend.core.models import ListingBase, ScrapingResult
from backend.core.exceptions import ParsingError, ScraperError

class NasdaqScraper(BaseScraper):
    """Scraper for NASDAQ new listings and IPOs."""

    def __init__(self):
        super().__init__()
        # Main URL for IPO listings
        self.url = "https://www.nasdaq.com/market-activity/ipos"
        # Alternative API endpoints that provide the data in JSON format
        self.api_url = "https://api.nasdaq.com/api/ipo/calendar"
        self.api_url_alt = "https://api.nasdaq.com/api/ipo/calendar?date=2025-03"  # Include a date parameter
        self.base_url = "https://www.nasdaq.com"
        
    async def scrape(self) -> ScrapingResult:
        """Scrape NASDAQ IPO listings."""
        try:
            self.logger.info(f"Starting NASDAQ IPO scraping from URL: {self.api_url}")
            
            # Common request headers
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            # Try the API endpoint first (more reliable)
            try:
                content = await self._make_request(
                    self.api_url,
                    headers=headers,
                    timeout=60  # Increased timeout to 60 seconds
                )
                
                self.logger.debug("Successfully retrieved NASDAQ IPO API data")
                listings = self.parse_api_data(content)
                
                if listings:
                    self.logger.info(f"Successfully parsed {len(listings)} IPO listings from NASDAQ API")
                    for listing in listings:
                        self.logger.debug(f"Found listing: {listing.name} ({listing.symbol}) - {listing.listing_date}")
                    
                    return ScrapingResult(
                        success=True,
                        message=f"Successfully scraped {len(listings)} listings from NASDAQ",
                        data=listings
                    )
            except asyncio.TimeoutError:
                self.logger.warning("Timeout accessing primary NASDAQ API endpoint. Trying alternative endpoint...")
            except Exception as e:
                self.logger.warning(f"Failed to fetch from primary NASDAQ API: {type(e).__name__}. Trying alternative endpoint...")
            
            # Try alternative API endpoint with date parameter
            try:
                self.logger.info(f"Trying alternative API endpoint: {self.api_url_alt}")
                content = await self._make_request(
                    self.api_url_alt,
                    headers=headers,
                    timeout=60
                )
                
                self.logger.debug("Successfully retrieved data from alternative NASDAQ API endpoint")
                listings = self.parse_api_data(content)
                
                if listings:
                    self.logger.info(f"Successfully parsed {len(listings)} IPO listings from alternative NASDAQ API")
                    for listing in listings:
                        self.logger.debug(f"Found listing: {listing.name} ({listing.symbol}) - {listing.listing_date}")
                    
                    return ScrapingResult(
                        success=True,
                        message=f"Successfully scraped {len(listings)} listings from NASDAQ using alt API",
                        data=listings
                    )
            except asyncio.TimeoutError:
                self.logger.warning("Timeout accessing alternative NASDAQ API endpoint. Falling back to HTML...")
            except Exception as e:
                self.logger.warning(f"Failed to fetch from alternative NASDAQ API: {type(e).__name__}. Falling back to HTML...")
            
            # Fallback: If we can't get the data from the API or parse it, try to scrape the HTML page
            self.logger.warning("API extraction failed, falling back to HTML scraping")
            
            # Execute the scraping directly
            result = await self.run_scraping_task()
            
            return result
        except Exception as e:
            # For truly unexpected errors, log a simple message without the stack trace in normal log
            error_msg = f"Failed to scrape NASDAQ: {type(e).__name__}"
            self.logger.error(error_msg)
            # Only include full trace in debug level
            self.logger.debug(f"Detailed error: {str(e)}", exc_info=True)
            
            # Return an empty result instead of raising an exception
            return ScrapingResult(
                success=False,
                message=f"Error scraping NASDAQ: {type(e).__name__}",
                data=[]
            )

    def parse_api_data(self, content: str) -> List[ListingBase]:
        """Parse the API JSON data to extract IPO listings."""
        try:
            data = json.loads(content)
            listings = []
            
            # Log the actual structure for debugging
            self.logger.debug(f"API response structure: {json.dumps(data, indent=2)[:500]}...")
            
            # Check if data structure is present
            if not data.get('data'):
                self.logger.warning(f"API response missing 'data' field: {json.dumps(data, indent=2)[:200]}...")
                return []
            
            # Check for priced IPOs section
            if 'priced' in data['data']:
                priced_data = data['data']['priced']
                self.logger.debug("Found 'priced' section in API response")
                
                # Check if there's a 'rows' field with actual IPO data
                if 'rows' in priced_data:
                    self.logger.debug(f"Found {len(priced_data['rows'])} priced IPO rows")
                    for row in priced_data['rows']:
                        try:
                            listing = self._create_listing_from_api_row(row, "Trading")
                            if listing:
                                listings.append(listing)
                        except Exception as e:
                            self.logger.warning(f"Error processing priced IPO row: {type(e).__name__}")
                else:
                    self.logger.debug("No 'rows' found in 'priced' section")
            
            # Check for upcoming IPOs section
            if 'upcoming' in data['data']:
                upcoming_data = data['data']['upcoming']
                self.logger.debug("Found 'upcoming' section in API response")
                
                # Check if there's a 'rows' field with actual IPO data
                if 'rows' in upcoming_data:
                    self.logger.debug(f"Found {len(upcoming_data['rows'])} upcoming IPO rows")
                    for row in upcoming_data['rows']:
                        try:
                            listing = self._create_listing_from_api_row(row, "Upcoming IPO")
                            if listing:
                                listings.append(listing)
                        except Exception as e:
                            self.logger.warning(f"Error processing upcoming IPO row: {type(e).__name__}")
                else:
                    self.logger.debug("No 'rows' found in 'upcoming' section")
            
            # Check for filings section as additional source
            if 'filings' in data['data']:
                filings_data = data['data']['filings']
                self.logger.debug("Found 'filings' section in API response")
                
                # Check if there's a 'rows' field with actual filing data
                if 'rows' in filings_data:
                    self.logger.debug(f"Found {len(filings_data['rows'])} filing rows")
                    for row in filings_data['rows']:
                        try:
                            listing = self._create_listing_from_api_row(row, "Filed IPO")
                            if listing:
                                listings.append(listing)
                        except Exception as e:
                            self.logger.warning(f"Error processing filing row: {type(e).__name__}")
                else:
                    self.logger.debug("No 'rows' found in 'filings' section")
            
            if not listings:
                self.logger.warning("No listings extracted from API response structure")
            
            return listings
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON data: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error in parse_api_data: {str(e)}")
            return []
            
    def _create_listing_from_api_row(self, row, status="Upcoming IPO") -> Optional[ListingBase]:
        """Create a ListingBase object from an API row."""
        try:
            # Extract data from row
            name = row.get('companyName', '').strip()
            
            # Skip rows without company name
            if not name:
                return None
                
            symbol = row.get('proposedTickerSymbol', '').strip()
            if not symbol:
                symbol = f"TBA-{name[:5] if len(name) >= 5 else name}"
            
            # Ensure symbol is valid and not too long for the database
            symbol = symbol[:20]  # Limit symbol length to avoid DB issues
            
            # Parse date
            date_str = row.get('pricingDate', '')
            if not date_str:
                date_str = row.get('expectedPriceDate', '')
            
            if date_str:
                try:
                    # Try different date formats
                    try:
                        listing_date = datetime.strptime(date_str, '%m/%d/%Y')
                    except ValueError:
                        try:
                            listing_date = datetime.strptime(date_str, '%Y-%m-%d')
                        except ValueError:
                            # Default to 30 days in the future if date parsing fails
                            listing_date = datetime.now() + timedelta(days=30)
                except Exception:
                    listing_date = datetime.now() + timedelta(days=30)
            else:
                # Default to 30 days in the future if no date provided
                listing_date = datetime.now() + timedelta(days=30)
            
            # Determine exchange
            exchange_text = row.get('exchange', '').strip()
            if not exchange_text:
                exchange_text = row.get('proposedExchange', '').strip()
                
            if "NASDAQ" in exchange_text.upper():
                exchange_code = "NASDAQ"
            elif "NYSE" in exchange_text.upper():
                exchange_code = "NYSE"
            else:
                exchange_code = "NASDAQ"  # Default
            
            # Get lot size from shares offered or use a reasonable default
            shares_text = row.get('sharesOffered', '1000').strip()
            try:
                lot_size = int(re.sub(r'[^\d]', '', shares_text)) if re.search(r'\d', shares_text) else 1000
                # Ensure lot_size is a valid positive integer
                if lot_size <= 0:
                    lot_size = 1000
            except Exception:
                lot_size = 1000
            
            # Determine status based on price information
            if status == "Trading" or row.get('offerPrice', ''):
                listing_status = "Trading"
            else:
                listing_status = status
            
            # Limit name length to avoid DB issues
            name = name[:100] if len(name) > 100 else name
            
            # Create listing object with valid data
            listing = ListingBase(
                name=name,
                symbol=symbol,
                listing_date=listing_date,
                lot_size=lot_size,
                status=listing_status,
                exchange_code=exchange_code,
                security_type="Equity",
                url=f"https://www.nasdaq.com/market-activity/stocks/{symbol.lower()}" if symbol else None,
                listing_detail_url=None  # Simplified to avoid potential URL validation issues
            )
            return listing
            
        except Exception as e:
            self.logger.warning(f"Error creating listing: {type(e).__name__}")
            self.logger.debug(f"Detailed error in _create_listing_from_api_row: {str(e)}", exc_info=True)
            return None

    def parse(self, content: str) -> List[ListingBase]:
        """Parse the HTML content and extract IPO listings."""
        try:
            self.logger.debug("Starting to parse NASDAQ IPO page content")
            soup = BeautifulSoup(content, 'html.parser')
            
            listings = []
            
            # Look for tables with IPO data (there might be different classes or IDs)
            tables = soup.find_all('table')
            
            if not tables:
                self.logger.warning("No tables found in the HTML content")
                
                # Try to find any IPO data in the page
                scripts = soup.find_all('script')
                for script in scripts:
                    script_text = script.string
                    if script_text and 'priceDate' in script_text:
                        self.logger.debug("Found IPO data in script tag")
                        # Try to extract JSON data from script
                        try:
                            # Look for JSON data in the script
                            match = re.search(r'(\[{.*}\])', script_text)
                            if match:
                                json_data = match.group(1)
                                data = json.loads(json_data)
                                for item in data:
                                    try:
                                        name = item.get('companyName', '')
                                        symbol = item.get('symbol', '')
                                        
                                        # Parse date
                                        date_str = item.get('priceDate', '')
                                        if date_str:
                                            try:
                                                listing_date = datetime.strptime(date_str, '%m/%d/%Y')
                                            except ValueError:
                                                listing_date = datetime.now() + timedelta(days=30)
                                        else:
                                            listing_date = datetime.now() + timedelta(days=30)
                                        
                                        exchange_code = "NASDAQ"  # Default
                                        if item.get('exchange'):
                                            if "NYSE" in item.get('exchange', '').upper():
                                                exchange_code = "NYSE"
                                        
                                        listing = ListingBase(
                                            name=name,
                                            symbol=symbol if symbol else f"TBA-{name[:5] if name else 'Unknown'}",
                                            listing_date=listing_date,
                                            lot_size=1000,  # Default
                                            status="Trading" if item.get('priceRange') else "Upcoming IPO",
                                            exchange_code=exchange_code,
                                            security_type="Equity",
                                            url=None,
                                            listing_detail_url=None
                                        )
                                        listings.append(listing)
                                    except Exception as e:
                                        self.logger.error(f"Error processing script data item: {str(e)}")
                        except Exception as e:
                            self.logger.error(f"Error extracting data from script: {str(e)}")
                
                return listings
            
            self.logger.debug(f"Found {len(tables)} tables in the HTML")
            
            # Process all tables that might contain IPO data
            for table in tables:
                try:
                    # Check if this table looks like an IPO table
                    headers = table.find_all('th')
                    header_text = ' '.join([h.text.strip() for h in headers])
                    
                    if 'Symbol' in header_text or 'Company' in header_text or 'Date' in header_text:
                        self.logger.debug("Found potential IPO table")
                        rows = table.find_all('tr')[1:]  # Skip header
                        for row in rows:
                            cols = row.find_all('td')
                            if len(cols) < 3:  # Need at least company, symbol, date
                                continue
                            
                            # Try to extract data from table
                            # This is simplified - adjust based on actual layout
                            name = cols[0].text.strip() if cols[0].text else "Unknown"
                            symbol = cols[1].text.strip() if len(cols) > 1 and cols[1].text else ""
                            
                            # Try to find a date
                            date_col = None
                            for i, col in enumerate(cols):
                                text = col.text.strip()
                                if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', text):
                                    date_col = i
                                    break
                            
                            if date_col is not None:
                                date_text = cols[date_col].text.strip()
                                match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', date_text)
                                if match:
                                    try:
                                        listing_date = datetime.strptime(match.group(1), '%m/%d/%Y')
                                    except ValueError:
                                        listing_date = datetime.now() + timedelta(days=30)
                                else:
                                    listing_date = datetime.now() + timedelta(days=30)
                            else:
                                listing_date = datetime.now() + timedelta(days=30)
                            
                            listing = ListingBase(
                                name=name,
                                symbol=symbol if symbol else f"TBA-{name[:5]}",
                                listing_date=listing_date,
                                lot_size=1000,  # Default
                                status="Upcoming IPO",
                                exchange_code="NASDAQ",  # Default
                                security_type="Equity",
                                url=None,
                                listing_detail_url=None
                            )
                            listings.append(listing)
                except Exception as e:
                    self.logger.error(f"Error processing table: {str(e)}")
            
            if not listings:
                self.logger.warning("No listings parsed from any tables")
            
            return listings
            
        except Exception as e:
            error_msg = f"Failed to parse NASDAQ content: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ParsingError(error_msg) from e
    
    async def get_filtered_listings(self, filter_type: str = 'all') -> pd.DataFrame:
        """Get listings with optional filtering."""
        result = await self.execute()
        if not result.success:
            return pd.DataFrame()

        df = pd.DataFrame([vars(listing) for listing in result.data])
        if df.empty:
            return df

        filters = {
            'upcoming': df['status'] == 'Upcoming IPO',
            'priced': df['status'] == 'Trading',
            'nasdaq_only': df['exchange_code'] == 'NASDAQ',
            'nyse_only': df['exchange_code'] == 'NYSE',
            'all': slice(None)
        }
        return df[filters.get(filter_type, slice(None))].copy()

    # Convenience methods
    async def get_upcoming_ipos(self) -> pd.DataFrame:
        """Get only upcoming IPOs."""
        return await self.get_filtered_listings('upcoming')

    async def get_priced_ipos(self) -> pd.DataFrame:
        """Get only priced IPOs."""
        return await self.get_filtered_listings('priced')

    async def get_nasdaq_listings(self) -> pd.DataFrame:
        """Get only NASDAQ listings."""
        return await self.get_filtered_listings('nasdaq_only')

    async def get_nyse_listings(self) -> pd.DataFrame:
        """Get only NYSE listings."""
        return await self.get_filtered_listings('nyse_only') 