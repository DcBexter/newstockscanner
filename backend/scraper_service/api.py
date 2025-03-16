"""API for the scraper service."""

import asyncio
import logging
import threading
from fastapi import FastAPI, BackgroundTasks, Query
from typing import Optional, Dict, Any

from backend.scraper_service.scraper import StockScanner
from backend.scraper_service.scrapers.hkex_scraper import HKEXScraper
from backend.scraper_service.scrapers.nasdaq_scraper import NasdaqScraper

# Set up logging
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Stock Scanner API")

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
        try:
            # Each scanner instance gets its own database connections
            scanner = StockScanner()
            # Run the scan with the provided exchange filter
            await scanner.run(exchange_filter=exchange_filter)
        except Exception as e:
            logger.error(f"Error during scan: {e}", exc_info=True)
        finally:
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
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}

def start_api():
    """Start the API server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

if __name__ == "__main__":
    start_api() 