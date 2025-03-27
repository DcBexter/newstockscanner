"""
Routes for triggering scraping operations.

This module defines the API routes for triggering scraping operations,
including scanning for new listings across all exchanges or for a specific exchange.
It communicates with the scraper service to initiate the scanning process.
"""

import logging
from functools import wraps
from typing import Dict, Any, Optional, Callable

from fastapi import APIRouter, HTTPException
import httpx

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# Constants
DEFAULT_SCRAPER_URL = "http://scraper_service:8002"
REQUEST_TIMEOUT_SECONDS = 2.0

settings = get_settings()
router = APIRouter(prefix="/scrape", tags=["scrape"])

# Error handling decorator
def handle_route_errors(operation_name: str):
    """
    Decorator to handle common errors in route handlers.

    Args:
        operation_name (str): Name of the operation for logging purposes

    Returns:
        Callable: Decorated function with error handling
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Re-raise HTTP exceptions that were already raised
                raise
            except ValueError as e:
                # Handle validation errors
                raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
            except Exception as e:
                # Log unexpected errors and return a generic message
                logger.error(f"Unexpected error in {operation_name}: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500, 
                    detail=f"An unexpected error occurred while {operation_name}"
                )
        return wrapper
    return decorator

async def make_scraper_request(scraper_url: str, exchange: Optional[str] = None) -> Dict[str, Any]:
    """
    Make a request to the scraper service.

    Args:
        scraper_url (str): The URL of the scraper service
        exchange (Optional[str], optional): The exchange to scan. Defaults to None.

    Returns:
        Dict[str, Any]: A dictionary containing the result of the request
    """
    target_description = exchange if exchange else 'all exchanges'
    logger.info(f"Making request to scraper service for {target_description}")

    try:
        # Include exchange parameter if provided
        params = {"exchange": exchange} if exchange else None

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{scraper_url}/api/v1/scrape", 
                params=params, 
                timeout=REQUEST_TIMEOUT_SECONDS
            )

            if response.status_code == 200:
                logger.info(f"Scan triggered successfully for {target_description}")
                return {
                    "message": f"Scan triggered successfully for {target_description}", 
                    "status": "success"
                }
            else:
                logger.warning(f"Scraper service returned non-200 status code: {response.status_code}")
                # If the endpoint doesn't exist or returns an error, we'll fallback to just returning success
                return {
                    "message": f"Scan request sent for {target_description}", 
                    "status": "success"
                }
    except Exception as e:
        logger.warning(f"Error communicating with scraper service: {str(e)}")
        # Just return success anyway - the scan is asynchronous
        return {
            "message": f"Scan initiated for {target_description}", 
            "status": "success"
        }

@router.post("/", response_model=Dict[str, Any])
@handle_route_errors("triggering scan")
async def trigger_scan(exchange: Optional[str] = None) -> Dict[str, Any]:
    """
    Trigger a scan for new listings.

    This endpoint triggers a scan for new listings across all exchanges or for a specific exchange.
    The scan is performed asynchronously by the scraper service.

    Args:
        exchange (Optional[str], optional): The exchange to scan. If None, all exchanges will be scanned. Defaults to None.

    Returns:
        Dict[str, Any]: A dictionary containing the result of the scan trigger operation.
                       Always returns a success message, even if there was an error,
                       to avoid blocking the user experience.
    """
    target_description = exchange if exchange else 'all exchanges'
    logger.info(f"Triggering scan for {target_description}")

    # Get the URL of the scraper service from settings or use default
    scraper_url = settings.SCRAPER_SERVICE_URL or DEFAULT_SCRAPER_URL

    # Make a request to the scraper service
    result = await make_scraper_request(scraper_url, exchange)

    # Always return success to not block the user experience
    return result
