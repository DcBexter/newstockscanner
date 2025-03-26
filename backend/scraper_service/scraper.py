"""
Stock Scanner module for scraping stock listings from various exchanges.

This module provides functionality to scan multiple stock exchanges for new listings,
save them to the database, and send notifications about new listings.
It supports continuous scanning at regular intervals and includes retry mechanisms
for handling temporary failures.
"""

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
    """
    Main class for scanning stock listings from various exchanges.

    This class orchestrates the process of scraping stock listings from different
    exchanges, saving them to the database, and sending notifications about new listings.
    It includes retry mechanisms for handling temporary failures and supports
    filtering by exchange.

    Attributes:
        MAX_RETRIES (int): Maximum number of retry attempts for failed scraping operations.
        RETRY_DELAY (int): Delay in seconds between retry attempts.
    """
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds

    def __init__(self):
        setup_logging(service_name="scraper_service")
        self.scraper_classes = {
            "hkex": HKEXScraper,
            "nasdaq": NasdaqScraper,
            "nyse": NasdaqScraper,  # Using NasdaqScraper for NYSE as it can extract NYSE listings too
            "fse": FrankfurtScraper  # Frankfurt Stock Exchange
        }
        self.db_service = DatabaseService()
        self.notification_service = NotificationService()

    async def __aenter__(self):
        """
        Enter async context.

        This method allows the StockScanner to be used as an async context manager.

        Returns:
            StockScanner: The StockScanner instance.
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit async context: properly close resources.

        This method is called when exiting the async context manager.
        Currently, there are no resources to clean up, but this method
        allows for future resource cleanup if needed.

        Args:
            exc_type: The exception type, if an exception was raised.
            exc_val: The exception value, if an exception was raised.
            exc_tb: The exception traceback, if an exception was raised.
        """
        # Currently no resources to clean up, but this method
        # allows for future resource cleanup if needed
        pass

    async def scan_listings(self, exchange_filter=None) -> List[Dict[str, Any]]:
        """
        Scan for new listings with retries across all scrapers.

        This method runs all applicable scrapers (or a filtered subset) to collect
        stock listings from various exchanges. It includes retry logic to handle
        temporary failures.

        Args:
            exchange_filter (str, optional): Filter to run only a specific exchange scraper.
                                            If None, all scrapers will be run. Defaults to None.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing the scraped listings.
        """
        all_listings = []
        scrapers_to_run = self._filter_scrapers(exchange_filter)

        # Run scrapers sequentially to ensure proper logging
        for name, scraper_class in scrapers_to_run.items():
            for attempt in range(self.MAX_RETRIES):
                try:
                    logger.info(f"Running {name} scraper (attempt {attempt + 1}/{self.MAX_RETRIES})...")

                    # Create a new scraper instance within the async context
                    try:
                        async with scraper_class() as scraper:
                            # Get date range for incremental scraping
                            if hasattr(self.settings, 'INCREMENTAL_SCRAPING_ENABLED') and self.settings.INCREMENTAL_SCRAPING_ENABLED:
                                start_date, end_date = scraper.get_incremental_date_range(name)
                                logger.info(f"Using incremental scraping for {name} from {start_date} to {end_date}")

                                # Pass date range to scraper if it supports it
                                if hasattr(scraper, 'scrape_with_date_range'):
                                    result = await scraper.scrape_with_date_range(start_date, end_date)
                                else:
                                    # Fall back to regular scraping
                                    result = await scraper.scrape()
                            else:
                                # Regular scraping
                                result = await scraper.scrape()

                            # Update last scrape time if successful
                            if result and result.success:
                                scraper.set_last_scrape_time(name)
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
                        listings = [listing.model_dump() for listing in result.data]
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
        """
        Filter scrapers based on the exchange filter.

        This method returns a subset of scrapers based on the exchange filter,
        or all scrapers if no filter is provided.

        Args:
            exchange_filter (str, optional): The exchange code to filter by.
                                           If None, all scrapers will be returned.

        Returns:
            Dict[str, type]: A dictionary mapping exchange codes to scraper classes.
        """
        if not exchange_filter:
            return self.scraper_classes

        if exchange_filter.lower() in self.scraper_classes:
            return {exchange_filter.lower(): self.scraper_classes[exchange_filter.lower()]}

        logger.warning(f"Unknown exchange filter: {exchange_filter}, falling back to all scrapers")
        return self.scraper_classes

    async def save_to_database(self, listings: List[Any]) -> Dict[str, Any]:
        """
        Save listings to the database using the database service.

        This method processes the listings to ensure they have the correct format
        and then saves them to the database.

        Args:
            listings (List[Any]): A list of listings to save. Each listing can be
                                 a dictionary or an object with a model_dump method.

        Returns:
            Dict[str, Any]: A dictionary containing the results of the save operation,
                           including counts of saved listings and new listings.
        """
        listing_dicts = []
        for listing in listings:
            listing_dict = listing if isinstance(listing, dict) else listing.model_dump()

            # Ensure exchange_code is set
            if not listing_dict.get("exchange_code"):
                if hasattr(listing, "exchange_code"):
                    listing_dict["exchange_code"] = listing.exchange_code
                elif isinstance(listing, dict) and 'exchange' in listing and 'code' in listing['exchange']:
                    listing_dict["exchange_code"] = listing['exchange']['code']

            listing_dicts.append(listing_dict)

        return await self.db_service.save_listings(listing_dicts)

    async def send_notifications(self, listings: List[Dict[str, Any]]) -> bool:
        """
        Send notifications for new stock listings.

        This method uses the notification service to send notifications about
        new stock listings.

        Args:
            listings (List[Dict[str, Any]]): A list of dictionaries containing
                                           the listings to send notifications for.

        Returns:
            bool: True if notifications were sent successfully, False otherwise.
        """
        return await self.notification_service.send_listing_notifications(listings)

    async def scan_and_process_exchanges(self, exchange_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Scan exchanges, save listings, and send notifications.

        This method orchestrates the entire process of scanning exchanges for new listings,
        saving them to the database, and sending notifications. It also checks for
        unnotified listings from previous runs.

        Args:
            exchange_filter (Optional[str], optional): Filter to run only a specific
                                                     exchange scraper. If None, all
                                                     scrapers will be run. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing the results of the operation,
                           including counts of all listings, saved listings,
                           new listings, and unnotified listings that were sent.
        """
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
        """
        Check for unnotified listings and send notifications.

        This method checks the database for listings that haven't been notified yet
        and sends notifications for them. It then marks the listings as notified.

        Returns:
            int: The number of unnotified listings that were successfully notified.
                 Returns 0 if no unnotified listings were found or if notifications failed.
        """
        try:
            async def get_and_process_unnotified(db):
                service = ListingService(db)

                try:
                    unnotified_listings = await service.get_unnotified_listings()
                except Exception as exc:
                    logger.error(f"Failed to get unnotified listings: {str(exc)}")
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
    """
    Continuously runs the scanner at regular intervals.

    This function creates a StockScanner instance and runs it in a loop,
    with a configurable delay between runs. It handles exceptions and
    ensures proper cleanup of resources.

    The interval between scans is controlled by the SCRAPING_INTERVAL_MINUTES
    environment variable, which defaults to 60 minutes if not set.
    """
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
            except Exception as ex:
                logger.error(f"Error during cleanup: {str(ex)}")

        # Close the loop
        loop.close() 
