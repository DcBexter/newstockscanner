from typing import List, Dict, Any, Optional
import logging
import json
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

from backend.scraper_service.scrapers.base import BaseScraper
from backend.core.models import ListingBase, ScrapingResult
from backend.core.exceptions import ParsingError, ScraperError

class FrankfurtScraper(BaseScraper):
    """Scraper for Frankfurt Stock Exchange (Börse Frankfurt) listings."""

    def __init__(self):
        super().__init__()
        # Base URL for Deutsche Börse Cash Market
        self.base_url = "https://www.deutsche-boerse-cash-market.com"
        
        # Frankfurt Stock Exchange announcements (the only reliable source for new listings)
        self.announcements_url = "https://www.deutsche-boerse-cash-market.com/dbcm-de/newsroom/fwb-bekanntmachungen/fwb-bekanntmachungen-ii"
        
    async def scrape(self) -> ScrapingResult:
        """Scrape Frankfurt Stock Exchange new listings."""
        try:
            self.logger.info(f"Starting Frankfurt Stock Exchange scraping")
            
            # German headers for better results with the German page
            german_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml"
            }
            
            # Get announcements that might contain listings
            self.logger.info(f"Scraping announcements: {self.announcements_url}")
            announcements_content = await self._make_request(
                self.announcements_url,
                headers=german_headers,
                timeout=60
            )
            
            # Parse the announcements
            listings = self.parse(announcements_content)
            
            if listings:
                self.logger.info(f"Successfully parsed {len(listings)} new listings from Frankfurt Stock Exchange")
                for listing in listings:
                    self.logger.debug(f"Found listing: {listing.name} ({listing.symbol}) - {listing.listing_date}")
                
                return ScrapingResult(
                    success=True,
                    message=f"Successfully scraped {len(listings)} listings from Frankfurt Stock Exchange",
                    data=listings
                )
            else:
                return ScrapingResult(
                    success=True,
                    message="No new listings found from Frankfurt Stock Exchange",
                    data=[]
                )
                
        except Exception as e:
            error_msg = f"Failed to scrape Frankfurt Stock Exchange: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            self.logger.debug("Detailed error:", exc_info=True)
            return ScrapingResult(
                success=False,
                message=error_msg,
                data=[]
            )
    
    def parse(self, content: str) -> List[ListingBase]:
        """Parse the announcements page for new listings."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            listings = []
            
            # Based on the actual HTML structure we can now see
            announcements = soup.select('ol.list.search-results > li')
            self.logger.info(f"Found {len(announcements)} announcements in the exact selector")
            
            # Log the titles of all announcements for debugging
            for i, announcement in enumerate(announcements):
                title_elem = announcement.select_one('.contentCol > h3 > a')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    self.logger.info(f"Announcement {i+1} title: {title}")
            
            # Process each announcement
            for announcement in announcements:
                try:
                    # Extract date from the date span
                    date_elem = announcement.select_one('.indexCol > .date')
                    date_text = date_elem.get_text(strip=True) if date_elem else ""
                    self.logger.debug(f"Date text: {date_text}")
                    
                    # Extract category 
                    category_elem = announcement.select_one('.contentCol > .categories')
                    category = category_elem.get_text(strip=True) if category_elem else ""
                    self.logger.debug(f"Category: {category}")
                    
                    # Extract announcement title and link
                    title_elem = announcement.select_one('.contentCol > h3 > a')
                    if not title_elem:
                        self.logger.debug("No title element found, skipping")
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    self.logger.debug(f"Processing title: {title}")
                    
                    # Important: ISIN is in a paragraph after the heading, not in the heading itself
                    isin_elem = announcement.select_one('.contentCol > p')
                    isin_text = isin_elem.get_text(strip=True) if isin_elem else ""
                    self.logger.debug(f"ISIN text: {isin_text}")
                    
                    # Extract ISIN from the paragraph text (format: "ISIN: US05526DCD57")
                    isin_match = re.search(r'ISIN:\s*([A-Z0-9]+)', isin_text)
                    if not isin_match:
                        self.logger.debug(f"No ISIN found in paragraph: {isin_text}")
                        
                        # Check if it's a "Diverse" ISIN
                        if "Diverse" in isin_text:
                            # For listings with multiple securities, create a meaningful ID
                            # Use the announcement type and date to make it unique
                            date_str = listing_date.strftime("%Y%m%d")
                            isin = f"DIVERSE-{date_str}-{announcement_type[:5]}".upper()
                            self.logger.debug(f"Using generated ISIN for diverse listing: {isin}")
                            
                            # For diverse listings, we'll still include them but mark accordingly
                            is_diverse = True
                        else:
                            # Still try to find an ISIN-like pattern in the title as fallback
                            title_isin_match = re.search(r'([A-Z]{2}[A-Z0-9]{10})', title)
                            if title_isin_match:
                                isin = title_isin_match.group(1)
                                self.logger.debug(f"Found ISIN in title: {isin}")
                            else:
                                self.logger.debug("No ISIN found, skipping")
                                continue
                    else:
                        isin = isin_match.group(1)
                        is_diverse = False
                        self.logger.debug(f"Found ISIN: {isin}")
                        
                    # Extract company name from the title
                    # Format is typically "Type : Company Name"
                    company_name = "Unknown"
                    if ":" in title:
                        parts = title.split(":", 1)  # Split on first colon only
                        if len(parts) > 1:
                            company_name = parts[1].strip()
                            self.logger.debug(f"Extracted company name: {company_name}")
                        
                    # If company is "Diverse", use a more descriptive name
                    if company_name.strip() == "Diverse":
                        # Use the announcement type (part before the colon) with security type
                        security_description = security_type if security_type != "Security" else "Securities"
                        company_name = f"Multiple {security_description} - {announcement_type}"
                        self.logger.debug(f"Using generated name for diverse listing: {company_name}")
                    
                    # Parse the date if available
                    listing_date = datetime.now()  # Default to today
                    if date_text:
                        # Format is "14. März 2025" (German format)
                        try:
                            # Replace German month names with numbers
                            german_months = {
                                'Januar': '01', 'Februar': '02', 'März': '03', 'April': '04',
                                'Mai': '05', 'Juni': '06', 'Juli': '07', 'August': '08',
                                'September': '09', 'Oktober': '10', 'November': '11', 'Dezember': '12'
                            }
                            
                            # Parse the German date format
                            parts = date_text.strip().split()
                            if len(parts) >= 3:
                                day = parts[0].strip('.') # Remove trailing period
                                month = german_months.get(parts[1], '01')  # Default to January if not found
                                year = parts[2]
                                
                                date_str = f"{day}.{month}.{year}"
                                listing_date = datetime.strptime(date_str, "%d.%m.%Y")
                                self.logger.debug(f"Parsed date: {listing_date}")
                            else:
                                self.logger.warning(f"Unexpected date format: {date_text}")
                        except Exception as e:
                            self.logger.warning(f"Could not parse date '{date_text}': {e}")
                    
                    # Extract information from category - determine if this is a stock, bond, etc.
                    security_type = "Security"  # Default
                    if category:
                        lower_category = category.lower()
                        if 'aktien' in lower_category:
                            security_type = "Equity"
                        elif 'anleihen' in lower_category:
                            security_type = "Bond"
                        elif 'strukturierte produkte' in lower_category:
                            security_type = "Structured Product"
                        self.logger.debug(f"Detected security type: {security_type}")
                    
                    # Determine if this is a new listing announcement
                    # Look for keywords that might indicate a new listing
                    lower_title = title.lower()
                    
                    # Extract the announcement type (like "Einbeziehung", "Wiederaufnahme")
                    announcement_type = ""
                    if ":" in lower_title:
                        announcement_type = lower_title.split(":", 1)[0].strip()
                        self.logger.debug(f"Announcement type: {announcement_type}")
                    
                    # Check if this is a listing we're interested in based on announcement type
                    is_new_listing = any(kw in lower_title for kw in [
                        'einbeziehung', 'zulassung', 'neuemission', 'ipo', 
                        'handelsaufnahme', 'börsengang', 'new listing', 'admission'
                    ])
                    
                    # These are all valid announcements, let's be inclusive
                    is_relevant = True  # Consider all announcements relevant
                    
                    if is_relevant:
                        # Construct the links for the frontend display
                        # 1. URL = announcement/PDF link (for info icon)
                        announcement_url = ""
                        if link:
                            # Links in the provided HTML appear to be absolute URLs already
                            if link.startswith('http'):
                                announcement_url = link
                            elif link.startswith('/'):
                                announcement_url = f"{self.base_url}{link}"
                            else:
                                announcement_url = f"{self.base_url}/{link}"
                        
                        # 2. Listing detail URL = Boerse Frankfurt search page with ISIN (for link icon)
                        detail_url = ""
                        if isin and not is_diverse:
                            # Use the ISIN as a search parameter for the Frankfurt search page
                            detail_url = f"https://www.boerse-frankfurt.de/suchergebnisse/{isin}"
                            self.logger.debug(f"Created detail URL with ISIN: {detail_url}")
                        else:
                            # If we don't have a valid ISIN, fallback to the main FSE page
                            detail_url = "https://www.boerse-frankfurt.de/"
                        
                        # Create appropriate status based on the announcement type and security type
                        status = "Unknown"
                        if "einbeziehung" in lower_title:
                            status = "New Listing"
                        elif "wiederaufnahme" in lower_title:
                            status = "Resumption of Trading"
                        elif "einstellung" in lower_title:
                            status = "Delisting"
                        else:
                            status = announcement_type.capitalize() if announcement_type else "Information"
                        
                        # Create the listing object
                        listing = ListingBase(
                            name=company_name,
                            symbol=isin,
                            listing_date=listing_date,
                            lot_size=1,
                            status=status,
                            exchange_code="FSE",
                            url=announcement_url,  # PDF link (for info icon)
                            security_type=security_type,
                            listing_detail_url=detail_url  # Search page link (for link icon)
                        )
                        
                        listings.append(listing)
                        self.logger.info(f"Extracted listing: {company_name} ({isin}) - Type: {security_type}, Status: {status}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse announcement: {str(e)}")
                    continue
            
            if not listings:
                self.logger.warning("No relevant listings found among the announcements")
            
            return listings
            
        except Exception as e:
            self.logger.error(f"Error parsing announcements page: {str(e)}")
            return [] 