"""
Routes for notification operations.

This module defines the API routes for notification operations, including
sending notifications and retrieving notification logs. It uses the
NotificationService to interact with the notification system and database.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import NotificationMessage
from backend.database.session import get_db
from backend.notification_service.service import NotificationService

logger = logging.getLogger(__name__)

# Constants
DEFAULT_NOTIFIER_TYPE = "telegram"
DEFAULT_LOG_DAYS = 7
DEFAULT_LOG_LIMIT = 100
MAX_LOG_LIMIT = 1000


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
                raise HTTPException(status_code=500, detail=f"An unexpected error occurred while {operation_name}")

        return wrapper

    return decorator


router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)


@router.post("/send", response_model=Dict[str, Any])
@handle_route_errors("sending notification")
async def send_notification(
    message: NotificationMessage, notifier_type: str = DEFAULT_NOTIFIER_TYPE, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Send a notification.

    This endpoint sends a notification using the specified notifier type.

    Args:
        message (NotificationMessage): The notification message to send.
        notifier_type (str, optional): The type of notifier to use. Defaults to "telegram".
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        Dict[str, Any]: A dictionary containing the result of the send operation.

    Raises:
        HTTPException: If there's an error sending the notification.
    """
    logger.info(f"Sending notification with title: {message.title} using {notifier_type} notifier")
    service = NotificationService(db)
    await service.initialize()
    result = await service.send(message, notifier_type)
    logger.info(f"Notification sent successfully: {result}")
    return result


@router.get("/logs", response_model=List[Dict[str, Any]])
@handle_route_errors("retrieving notification logs")
async def get_notification_logs(
    status: Optional[str] = None, days: int = DEFAULT_LOG_DAYS, limit: int = DEFAULT_LOG_LIMIT, db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get notification logs with optional filters.

    This endpoint retrieves notification logs from the database with optional
    filters for status, time period, and limit.

    Args:
        status (Optional[str], optional): Filter by notification status. Defaults to None.
        days (int, optional): Get logs from the last N days. Defaults to 7.
        limit (int, optional): Maximum number of logs to return. Defaults to 100.
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        List[Dict[str, Any]]: A list of notification logs.

    Raises:
        HTTPException: If there's an error retrieving logs from the database or
                      if the parameters are invalid.
    """
    # Validate parameters
    if days <= 0:
        raise HTTPException(status_code=400, detail="days must be a positive integer")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be a positive integer")
    if limit > MAX_LOG_LIMIT:
        raise HTTPException(status_code=400, detail=f"limit must not exceed {MAX_LOG_LIMIT}")

    logger.info(f"Retrieving notification logs with status={status}, days={days}, limit={limit}")
    service = NotificationService(db)
    logs = await service.get_logs(status, days, limit)
    logger.info(f"Retrieved {len(logs)} notification logs")
    return logs
