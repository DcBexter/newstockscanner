import asyncio
from typing import List, Dict, Any, Optional
import logging
import os

from backend.scraper_service.scrapers.hkex_scraper import HKEXScraper
from backend.scraper_service.scrapers.nasdaq_scraper import NasdaqScraper
from backend.scraper_service.scrapers.frankfurt_scraper import FrankfurtScraper
from backend.api_service.services import ListingService
from backend.config.logging import setup_logging
from backend.scraper_service.services import DatabaseService, DatabaseHelper, NotificationService

logger = logging.getLogger(__name__)

class StockScanner:
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds

    def __init__(self):
        setup_logging()
        self.scraper_classes = {
            "hkex": HKEXScraper,
            "nasdaq": NasdaqScraper,
            "nyse": NasdaqScraper,  # Using NasdaqScraper for NYSE as it can extract NYSE listings too
            "fse": FrankfurtScraper  # Frankfurt Stock Exchange
        }
        self.db_service = DatabaseService()
        self.notification_service = NotificationService()

    async def __aenter__(self):
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context: properly close resources."""
        # Currently no resources to clean up, but this method
        # allows for future resource cleanup if needed
        pass

    async def scan_listings(self, exchange_filter=None) -> List[Dict[str, Any]]:
        """Scan for new listings with retries across all scrapers."""
        all_listings = []
        scrapers_to_run = self._filter_scrapers(exchange_filter)

        # Run scrapers sequentially to ensure proper logging
        for name, scraper_class in scrapers_to_run.items():
            for attempt in range(self.MAX_RETRIES):
                try:
                    logger.info(f"Running {name} scraper (attempt {attempt + 1}/{self.MAX_RETRIES})...")

                    # Create a new scraper instance within the async context
                    result = None
                    try:
                        async with scraper_class() as scraper:
                            result = await scraper.scrape()
                    except Exception as session_err:
                        logger.error(f"Error managing session for {name}: {str(session_err)}")
                        if attempt < self.MAX_RETRIES - 1:
                            logger.warning(f"Session error for {name}. Retrying in {self.RETRY_DELAY} seconds...")
                            await asyncio.sleep(self.RETRY_DELAY)
                            continue
                        break

                    # Process result if valid
                    if not result:
                        if attempt < self.MAX_RETRIES - 1:
                            await asyncio.sleep(self.RETRY_DELAY)
                            continue
                        break

                    if result.success:
                        listings = [listing.dict() for listing in result.data]
                        logger.info(f"Found {len(listings)} listings from {name}")
                        all_listings.extend(listings)
                        break
                    elif attempt < self.MAX_RETRIES - 1:
                        logger.warning(f"Failed to scan {name}: {result.message}. Retrying...")
                        await asyncio.sleep(self.RETRY_DELAY)
                    else:
                        logger.error(f"Failed to scan {name} after {self.MAX_RETRIES} attempts")

                except Exception as e:
                    logger.error(f"Error scraping {name}: {str(e)}")
                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(self.RETRY_DELAY)

        logger.info(f"Total listings found across all scrapers: {len(all_listings)}")
        return all_listings

    def _filter_scrapers(self, exchange_filter):
        """Filter scrapers based on the exchange filter."""
        if not exchange_filter:
            return self.scraper_classes

        if exchange_filter.lower() in self.scraper_classes:
            return {exchange_filter.lower(): self.scraper_classes[exchange_filter.lower()]}

        logger.warning(f"Unknown exchange filter: {exchange_filter}, falling back to all scrapers")
        return self.scraper_classes

    async def save_to_database(self, listings: List[Any]) -> Dict[str, Any]:
        """Save listings to the database using the database service."""
        listing_dicts = []
        for listing in listings:
            listing_dict = listing if isinstance(listing, dict) else listing.dict()

            # Ensure exchange_code is set
            if not listing_dict.get("exchange_code"):
                if hasattr(listing, "exchange_code"):
                    listing_dict["exchange_code"] = listing.exchange_code
                elif isinstance(listing, dict) and 'exchange' in listing and 'code' in listing['exchange']:
                    listing_dict["exchange_code"] = listing['exchange']['code']

            listing_dicts.append(listing_dict)

        return await self.db_service.save_listings(listing_dicts)

    async def send_notifications(self, listings: List[Dict[str, Any]]) -> bool:
        """Send notifications for new stock listings."""
        return await self.notification_service.send_listing_notifications(listings)

    async def scan_and_process_exchanges(self, exchange_filter: Optional[str] = None) -> Dict[str, Any]:
        """Scan exchanges, save listings, and send notifications."""
        logger_msg = f"{exchange_filter.upper()}-only scan" if exchange_filter else "multiple exchanges"
        logger.info(f"Starting stock scanner with {logger_msg}...")

        # Step 1: Collect listings from scrapers
        all_listings = await self.scan_listings(exchange_filter)
        logger.info(f"Found {len(all_listings)} total listings from all sources")

        # Step 2: Save listings to database
        result = await self.save_to_database(all_listings)

        # Step 3: Check for unnotified listings from previous runs
        unnotified = await self.check_and_notify_unnotified()

        # Step 4: Send notifications for new listings if needed
        if result.get("new_listings") and unnotified == 0:
            logger.info(f"Sending notifications for {len(result['new_listings'])} new listings")
            await self.send_notifications(result["new_listings"])
        elif result.get("new_listings"):
            logger.info(f"Skipping notifications for {len(result['new_listings'])} new listings (already processed)")
        else:
            logger.info("No new listings to notify about")

        logger.info("Scanner run completed")

        return {
            "all_listings": len(all_listings),
            "saved_count": result.get("saved_count", 0),
            "new_listings": len(result.get("new_listings", [])),
            "unnotified_sent": unnotified
        }

    async def check_and_notify_unnotified(self) -> int:
        """Check for unnotified listings and send notifications."""
        try:
            async def get_and_process_unnotified(db):
                service = ListingService(db)

                try:
                    unnotified_listings = await service.get_unnotified_listings()
                except Exception as e:
                    logger.error(f"Failed to get unnotified listings: {str(e)}")
                    return 0

                if not unnotified_listings:
                    logger.info("No unnotified listings found")
                    return 0

                logger.info(f"Found {len(unnotified_listings)} unnotified listings from previous runs")

                # Convert to dictionaries for notification service
                listings_to_notify = [{
                    "id": listing.id,
                    "name": listing.name,
                    "symbol": listing.symbol,
                    "listing_date": listing.listing_date,
                    "lot_size": listing.lot_size,
                    "status": listing.status,
                    "exchange_code": listing.exchange.code,
                    "url": listing.url,
                    "security_type": listing.security_type,
                    "listing_detail_url": listing.listing_detail_url
                } for listing in unnotified_listings]

                # Send notifications
                if await self.send_notifications(listings_to_notify):
                    # Mark all as notified
                    for listing in unnotified_listings:
                        await service.mark_as_notified(listing.id)

                    logger.info(f"Successfully sent notifications for {len(unnotified_listings)} unnotified listings")
                    return len(unnotified_listings)
                else:
                    logger.warning("Failed to send notifications for unnotified listings")
                    return 0

            return await DatabaseHelper.execute_db_operation(get_and_process_unnotified)

        except Exception as e:
            logger.error(f"Error checking unnotified listings: {str(e)}")
            return 0

async def start_continuous_scanning_loop():
    """Continuously runs the scanner at regular intervals."""
    while True:
        try:
            # Use StockScanner as a context manager to ensure proper resource cleanup
            async with StockScanner() as scanner:
                await scanner.scan_and_process_exchanges()

            interval_minutes = int(os.getenv("SCRAPING_INTERVAL_MINUTES", 60))
            logger.info(f"Waiting {interval_minutes} minutes until next scan...")
            await asyncio.sleep(interval_minutes * 60)

        except Exception as e:
            logger.error(f"Error in scanning loop: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying
        except KeyboardInterrupt:
            logger.info("Scanner stopped by user")
            break

if __name__ == "__main__":
    # Use a dedicated event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_continuous_scanning_loop())
    except KeyboardInterrupt:
        logger.info("Scanner stopped by user")
    finally:
        # Clean up any pending tasks
        pending = asyncio.all_tasks(loop=loop)
        for task in pending:
            task.cancel()

        # Allow tasks to finish cancellation
        if pending:
            try:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

        # Close the loop
        loop.close() 
