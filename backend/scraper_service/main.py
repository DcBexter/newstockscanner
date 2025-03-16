"""Main entry point for the scraper service."""

import asyncio
import logging
import os
import threading
from typing import Optional

from backend.config.logging import setup_logging
from backend.scraper_service.api import start_api
from backend.scraper_service.scraper import StockScanner, start_continuous_scanning_loop

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

# Create a single global event loop for async operations
global_loop = None

def start_api_server():
    """Start the API server in a separate thread."""
    logger.info("Starting API server...")
    start_api()

def start_scheduler():
    """Start the continuous scanning scheduler in the main thread."""
    logger.info("Starting scheduler...")
    # Create a new event loop for the main scheduler thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    global global_loop
    global_loop = loop
    
    try:
        loop.run_until_complete(start_continuous_scanning_loop())
    except Exception as e:
        logger.error(f"Error in scheduler: {e}")
    finally:
        loop.close()

def process_unnotified_listings():
    """Process any unnotified listings and send notifications."""
    logger.info("Checking for unnotified listings...")
    stock_scanner = StockScanner()
    
    # Create a dedicated event loop for this background task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        unnotified_count = loop.run_until_complete(stock_scanner.check_and_notify_unnotified())
        if unnotified_count > 0:
            logger.info(f"Sent notifications for {unnotified_count} previously unnotified listings")
        else:
            logger.info("No unnotified listings found")
    except Exception as e:
        logger.error(f"Error checking unnotified listings: {e}")
    finally:
        # Make sure to close the loop to free resources
        try:
            # Cancel all running tasks
            pending = asyncio.all_tasks(loop=loop)
            if pending:
                for task in pending:
                    task.cancel()
                # Allow canceled tasks to complete with a timeout
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            logger.error(f"Error canceling tasks: {e}")
        finally:
            loop.close()

def main():
    """Main entry point for the scraper service."""
    # Determine which components to run based on environment variables
    run_api = os.getenv("RUN_API", "true").lower() == "true"
    run_scheduler_flag = os.getenv("RUN_SCHEDULER", "true").lower() == "true"
    check_unnotified = os.getenv("CHECK_UNNOTIFIED", "true").lower() == "true"

    logger.info(f"Starting scraper service with API: {run_api}, Scheduler: {run_scheduler_flag}")

    # Check for unnotified listings on startup if enabled
    if check_unnotified:
        unnotified_thread = threading.Thread(target=process_unnotified_listings, daemon=True)
        unnotified_thread.start()
        logger.info("Started check for unnotified listings in background")

    if run_api and run_scheduler_flag:
        # Run both API and scheduler
        # API runs in a separate thread, scheduler in the main thread
        api_thread = threading.Thread(target=start_api_server, daemon=True)
        api_thread.start()
        start_scheduler()
    elif run_api:
        # Run only the API
        start_api_server()
    elif run_scheduler_flag:
        # Run only the scheduler
        start_scheduler()
    else:
        logger.error("Neither API nor scheduler enabled. Nothing to run.")

if __name__ == "__main__":
    main() 