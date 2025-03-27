"""
Routes for statistics operations.

This module defines the API routes for statistics operations, including
retrieving listing statistics with filters. It uses the StatsService to
interact with the database and generate statistics.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api_service.services import StatsService
from backend.core.exceptions import DatabaseQueryError
from backend.database.session import get_db

logger = logging.getLogger(__name__)


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
            except DatabaseQueryError as e:
                # Handle database query errors
                logger.error(f"Database error in {operation_name}: {str(e)}")
                raise HTTPException(status_code=400, detail=str(e))
            except ValueError as e:
                # Handle validation errors
                raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
            except Exception as e:
                # Log unexpected errors and return a generic message
                logger.error(f"Unexpected error in {operation_name}: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"An unexpected error occurred while {operation_name}")

        return wrapper

    return decorator


router = APIRouter(
    prefix="/statistics",
    tags=["statistics"],
)


@router.get("/", response_model=Dict[str, Any])
@handle_route_errors("retrieving statistics")
async def get_listing_stats(days: int = 30, exchange_code: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    Get listing statistics with optional filters.

    This endpoint retrieves statistics about stock listings for the specified period.
    It supports filtering by exchange code and allows specifying the number of days
    to include in the statistics.

    Args:
        days (int, optional): Number of days to include in the statistics. Defaults to 30.
        exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        Dict[str, Any]: A dictionary containing the statistics, including:
            - total: Total number of listings in the specified period
            - total_all_time: Total number of listings across all time
            - statuses: Counts of listings by status
            - security_types: Counts of listings by security type
            - daily_stats: Daily counts of new listings
            - exchange_stats: Counts of listings by exchange

    Raises:
        HTTPException: If there's an error retrieving statistics from the database.
    """
    service = StatsService(db)
    return await service.get_listing_stats(days, exchange_code)
