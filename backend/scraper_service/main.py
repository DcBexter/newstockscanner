"""Main entry point for the scraper service."""

import asyncio
import logging
import os
import threading

from backend.config.logging import setup_logging
from backend.scraper_service.api import start_api
from backend.scraper_service.scraper import StockScanner, start_continuous_scanning_loop

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

def start_api_server():
    """Start the API server in a separate thread."""
    logger.info("Starting API server...")
    start_api()

def start_scheduler():
    """Start the continuous scanning scheduler in the main thread."""
    logger.info("Starting scheduler...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(start_continuous_scanning_loop())
    except Exception as e:
        logger.error(f"Error in scheduler: {e}")
    finally:
        loop.close()

def process_unnotified_listings():
    """Process any unnotified listings and send notifications."""
    logger.info("Checking for unnotified listings...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Use StockScanner as a context manager to ensure proper resource cleanup
        async def run_with_context():
            async with StockScanner() as stock_scanner:
                return await stock_scanner.check_and_notify_unnotified()

        unnotified_count = loop.run_until_complete(run_with_context())
        if unnotified_count > 0:
            logger.info(f"Sent notifications for {unnotified_count} previously unnotified listings")
        else:
            logger.info("No unnotified listings found")
    except Exception as e:
        logger.error(f"Error checking unnotified listings: {e}")
    finally:
        try:
            pending = asyncio.all_tasks(loop=loop)
            if pending:
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()

def main():
    """Main entry point for the scraper service."""
    # Determine which components to run based on environment variables
    run_api = os.getenv("RUN_API", "true").lower() == "true"
    run_scheduler = os.getenv("RUN_SCHEDULER", "true").lower() == "true"
    check_unnotified = os.getenv("CHECK_UNNOTIFIED", "true").lower() == "true"

    logger.info(f"Starting scraper service with API: {run_api}, Scheduler: {run_scheduler}")

    # Check for unnotified listings on startup if enabled
    if check_unnotified:
        unnotified_thread = threading.Thread(target=process_unnotified_listings, daemon=True)
        unnotified_thread.start()
        logger.info("Started check for unnotified listings in background")

    if run_api and run_scheduler:
        # Run both API and scheduler
        api_thread = threading.Thread(target=start_api_server, daemon=True)
        api_thread.start()
        start_scheduler()
    elif run_api:
        # Run only the API
        start_api_server()
    elif run_scheduler:
        # Run only the scheduler
        start_scheduler()
    else:
        logger.error("Neither API nor scheduler enabled. Nothing to run.")

if __name__ == "__main__":
    main() 
