"""
Routes for exchange operations.

This module defines the API routes for exchange operations, including
retrieving all exchanges, getting a specific exchange by code,
and creating new exchanges. It uses the ExchangeService to interact with
the database.
"""

import logging
from functools import wraps
from typing import Any, Callable, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api_service.services import ExchangeService
from backend.core.models import Exchange, ExchangeCreate
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
    prefix="/exchanges",
    tags=["exchanges"],
)


@router.get("/", response_model=List[Exchange])
@handle_route_errors("retrieving exchanges")
async def get_exchanges(db: AsyncSession = Depends(get_db)) -> List[Exchange]:
    """
    Get all exchanges.

    This endpoint retrieves all exchanges from the database.

    Args:
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        List[Exchange]: A list of all exchanges.

    Raises:
        HTTPException: If there's an error retrieving exchanges from the database.
    """
    logger.info("Retrieving all exchanges")
    service = ExchangeService(db)
    exchanges = await service.get_all()
    logger.info(f"Retrieved {len(exchanges)} exchanges")
    return exchanges


@router.get("/{code}", response_model=Exchange)
@handle_route_errors("retrieving exchange by code")
async def get_exchange(code: str, db: AsyncSession = Depends(get_db)) -> Exchange:
    """
    Get exchange by code.

    This endpoint retrieves a specific exchange from the database by its code.

    Args:
        code (str): The code of the exchange to retrieve.
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        Exchange: The Exchange object if found.

    Raises:
        HTTPException: If the exchange is not found or if there's an error
                      retrieving the exchange from the database.
    """
    logger.info(f"Retrieving exchange with code: {code}")
    service = ExchangeService(db)
    exchange = await service.get_by_code(code)
    if not exchange:
        logger.warning(f"Exchange with code {code} not found")
        raise HTTPException(status_code=404, detail="Exchange not found")
    logger.info(f"Retrieved exchange: {exchange.name} ({exchange.code})")
    return exchange


@router.post("/", response_model=Exchange)
@handle_route_errors("creating exchange")
async def create_exchange(exchange: ExchangeCreate, db: AsyncSession = Depends(get_db)) -> Exchange:
    """
    Create a new exchange.

    This endpoint creates a new exchange in the database.

    Args:
        exchange (ExchangeCreate): The exchange data to create.
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        Exchange: The created Exchange object.

    Raises:
        HTTPException: If there's an error creating the exchange in the database,
                      such as if an exchange with the same code already exists.
    """
    logger.info(f"Creating new exchange: {exchange.name} ({exchange.code})")
    service = ExchangeService(db)
    new_exchange = await service.create(exchange)
    logger.info(f"Created new exchange: {new_exchange.name} ({new_exchange.code})")
    return new_exchange
