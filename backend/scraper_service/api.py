"""API for the scraper service."""

import asyncio
import logging
import threading
import time
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, Query, Depends
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.scraper_service.scraper import StockScanner
from backend.scraper_service.scrapers.hkex_scraper import HKEXScraper
from backend.scraper_service.scrapers.nasdaq_scraper import NasdaqScraper
from backend.database.session import get_db
from backend.config.settings import get_settings

# Set up logging
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Import metrics module (requires prometheus_client to be installed)
try:
    from backend.core.metrics import setup_metrics, metrics
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    logger.warning("Prometheus client not installed. Metrics collection is disabled.")
    logger.warning("To enable metrics, install prometheus-client: pip install prometheus-client")

# Create FastAPI app
app = FastAPI(title="Stock Scanner API")

# Set up metrics collection if enabled
if METRICS_ENABLED:
    logger.info("Setting up metrics collection")
    setup_metrics(app)

    # Add scraper-specific metrics
    metrics.counter('scraper_runs_total', 'Total number of scraper runs', ['exchange'])
    metrics.counter('scraper_listings_found_total', 'Total number of listings found', ['exchange'])
    metrics.counter('scraper_errors_total', 'Total number of scraper errors', ['exchange', 'error_type'])
    metrics.histogram('scraper_run_duration_seconds', 'Duration of scraper runs in seconds', ['exchange'])
    metrics.gauge('scraper_last_run_timestamp', 'Timestamp of the last scraper run', ['exchange'])
else:
    logger.info("Metrics collection is disabled")

def execute_coroutine_in_thread(coroutine):
    """Execute a coroutine in a dedicated event loop in a separate thread.

    This ensures that async operations can run safely without interfering with the main thread's event loop.
    """
    def _run_in_thread():
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create a separate task for the coroutine
            main_task = asyncio.ensure_future(coroutine, loop=loop)

            # Run until the main task is complete
            loop.run_until_complete(main_task)

        except Exception as e:
            logger.error(f"Error in background task: {e}", exc_info=True)
        finally:
            # Record the thread ID for logging
            thread_id = threading.get_ident()
            logger.debug(f"Cleaning up resources for thread {thread_id}")

            # Clean up resources in a way that prevents event loop issues
            try:
                # Cancel all pending tasks
                pending = asyncio.all_tasks(loop)
                if pending:
                    for task in pending:
                        task.cancel()

                    # Give tasks time to acknowledge cancellation
                    loop.run_until_complete(asyncio.sleep(0.1))

                    # Now gather them with a timeout to avoid waiting forever
                    try:
                        loop.run_until_complete(
                            asyncio.wait(pending, timeout=1.0, return_when=asyncio.ALL_COMPLETED)
                        )
                    except Exception as wait_error:
                        logger.debug(f"Error waiting for tasks to complete: {wait_error}")

                # Ensure async generators are properly shut down
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception as shutdown_error:
                    logger.debug(f"Error shutting down async generators: {shutdown_error}")

                # Define a proper database cleanup function that doesn't try to use imported functions
                # This prevents the "Future attached to a different loop" error
                async def close_resources():
                    # Close any db connections that might be in this task's context
                    # But avoid importing external functions that might create tasks in other loops
                    try:
                        # Get all database-related tasks and gracefully close them
                        for task in asyncio.all_tasks(loop):
                            if 'database' in str(task) or 'db' in str(task) or 'sql' in str(task):
                                logger.debug(f"Cancelling database task: {task}")
                                task.cancel()
                    except Exception as e:
                        logger.debug(f"Error during database resource cleanup: {e}")

                # Run our local cleanup function in this loop
                try:
                    loop.run_until_complete(close_resources())
                except Exception as resource_error:
                    logger.debug(f"Error during resource cleanup: {resource_error}")

                # Run a quick sleep to allow any final callbacks to process
                try:
                    loop.run_until_complete(asyncio.sleep(0.1))
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error during cleanup: {e}", exc_info=True)
            finally:
                # Stop the loop before closing it
                try:
                    loop.stop()
                except Exception as e:
                    logger.debug(f"Error stopping loop: {e}")

                # Now it's safe to close the loop
                try:
                    loop.close()
                except Exception as e:
                    logger.debug(f"Error closing loop: {e}")

                logger.debug(f"Thread {thread_id} cleanup completed")

    # Start the function in a new thread
    thread = threading.Thread(target=_run_in_thread)
    thread.daemon = True
    thread.start()
    return thread

@app.post("/api/v1/scrape")
@app.post("/api/v1/scrape/")
async def scan(
    background_tasks: BackgroundTasks,
    exchange: Optional[str] = Query(None, description="Specific exchange to scan (e.g., 'hkex', 'nasdaq')")
) -> Dict[str, Any]:
    """
    Trigger a scan for new listings.

    Args:
        background_tasks: FastAPI background tasks
        exchange: Optional specific exchange to scan

    Returns:
        Dict with status and message
    """
    # Normalize exchange name if provided
    exchange_filter = None
    if exchange:
        exchange_filter = exchange.lower()
        logger.info(f"Scan request received for exchange: {exchange_filter}")
    else:
        logger.info("Scan request received for all exchanges")

    # Create an isolated async function that creates its own scanner instance
    async def isolated_scan():
        start_time = time.time()
        exchange_name = exchange_filter or "all"

        # Record metrics if enabled
        if METRICS_ENABLED:
            metrics.counter('scraper_runs_total').labels(exchange_name).inc()
            metrics.gauge('scraper_last_run_timestamp').labels(exchange_name).set_to_current_time()

        try:
            # Each scanner instance gets its own database connections
            scanner = StockScanner()
            # Run the scan with the provided exchange filter
            result = await scanner.run(exchange_filter=exchange_filter)

            # Record success metrics if enabled
            if METRICS_ENABLED and result:
                # Record the number of listings found
                listings_count = result.get('all_listings', 0)
                metrics.counter('scraper_listings_found_total').labels(exchange_name).inc(listings_count)

        except Exception as e:
            logger.error(f"Error during scan: {e}", exc_info=True)

            # Record error metrics if enabled
            if METRICS_ENABLED:
                error_type = type(e).__name__
                metrics.counter('scraper_errors_total').labels(exchange_name, error_type).inc()

        finally:
            # Record duration metrics if enabled
            if METRICS_ENABLED:
                duration = time.time() - start_time
                metrics.histogram('scraper_run_duration_seconds').labels(exchange_name).observe(duration)

            # Explicitly clean up scanner resources if possible
            if 'scanner' in locals():
                try:
                    # If the scanner has a cleanup method, call it
                    if hasattr(scanner, 'cleanup') and callable(scanner.cleanup):
                        await scanner.cleanup()
                    # If the scanner has a close method, call it
                    elif hasattr(scanner, 'close') and callable(scanner.close):
                        await scanner.close()
                except Exception as cleanup_error:
                    logger.error(f"Error during scanner cleanup: {cleanup_error}", exc_info=True)

    # Run the scan in a dedicated thread with its own event loop
    execute_coroutine_in_thread(isolated_scan())

    return {
        "status": "success",
        "message": f"Scan for {exchange if exchange else 'all exchanges'} initiated"
    }

@app.get("/api/v1/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Health check endpoint to verify that the scraper service and its dependencies are working.

    This endpoint checks the database connection and returns information about
    the service status. It can be used by monitoring tools to verify that the
    service is operational.

    Args:
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        dict: A dictionary containing the service status and dependency statuses.
    """
    logger.debug("Health check requested")

    # Check database connection
    db_status = "connected"
    try:
        # Simple database query to verify connection
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = f"error: {str(e)}"

    # Check if scrapers are available
    scrapers_status = {}
    for name, scraper_class in {
        "hkex": HKEXScraper,
        "nasdaq": NasdaqScraper
    }.items():
        try:
            # Just check if the class can be instantiated
            scraper_instance = scraper_class()
            scrapers_status[name] = "available"
        except Exception as e:
            logger.error(f"Scraper {name} health check failed: {str(e)}")
            scrapers_status[name] = f"error: {str(e)}"

    # Overall status is healthy only if all dependencies are working
    overall_status = "healthy"
    if db_status != "connected" or any(status != "available" for status in scrapers_status.values()):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "service": "scraper",
        "dependencies": {
            "database": db_status,
            "scrapers": scrapers_status
        },
        "timestamp": datetime.now().isoformat()
    }

def start_api():
    """Start the API server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

if __name__ == "__main__":
    start_api() 
