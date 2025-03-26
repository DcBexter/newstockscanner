"""
Routes for stock listing operations.

This module defines the API routes for stock listing operations, including
retrieving listings with filters, getting a specific listing by symbol,
and creating new listings. It uses the ListingService to interact with
the database.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api_service.services import ListingService
from backend.core.models import Listing, ListingCreate, PaginatedListings
from backend.database.session import get_db
from backend.database.models import StockListing

# Utility function to convert database models to Pydantic models
def convert_db_listing_to_model(db_listing: StockListing) -> Listing:
    """
    Convert a database StockListing model to a Pydantic Listing model.

    Args:
        db_listing (StockListing): The database model to convert

    Returns:
        Listing: The converted Pydantic model
    """
    return Listing(
        id=db_listing.id,
        name=db_listing.name,
        symbol=db_listing.symbol,
        listing_date=db_listing.listing_date,
        lot_size=db_listing.lot_size,
        status=db_listing.status,
        exchange_code=db_listing.exchange.code,
        url=db_listing.url,
        security_type=db_listing.security_type,
        listing_detail_url=db_listing.listing_detail_url,
        created_at=db_listing.created_at,
        updated_at=db_listing.updated_at
    )

def convert_db_listings_to_models(db_listings: List[StockListing]) -> List[Listing]:
    """
    Convert a list of database StockListing models to a list of Pydantic Listing models.

    Args:
        db_listings (List[StockListing]): The database models to convert

    Returns:
        List[Listing]: The converted Pydantic models
    """
    return [convert_db_listing_to_model(listing) for listing in db_listings]

router = APIRouter(
    prefix="/listings",
    tags=["listings"],
)

@router.get("/", response_model=PaginatedListings)
async def get_listings(
    exchange_code: Optional[str] = None,
    status: Optional[str] = None,
    days: Optional[int] = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Get listings with optional filters and pagination.

    This endpoint retrieves stock listings from the database with optional filters
    for exchange code, status, and time period. It supports filtering by either
    a specific date range or by the number of days from the current date.
    It also supports pagination and returns the total count of matching records.

    Args:
        exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
        status (Optional[str], optional): Filter by listing status. Defaults to None.
        days (Optional[int], optional): Get listings from the last N days. Defaults to 30.
        start_date (Optional[str], optional): Get listings from this date (format: YYYY-MM-DD). Defaults to None.
        end_date (Optional[str], optional): Get listings up to this date (format: YYYY-MM-DD). Defaults to None.
        skip (int, optional): Number of records to skip. Defaults to 0.
        limit (int, optional): Maximum number of records to return. Defaults to 100.
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        PaginatedListings: An object containing the paginated listings and total count.

    Raises:
        HTTPException: If there's an error with the date format or date range,
                      or if there's an error retrieving listings from the database.
    """
    service = ListingService(db)
    try:
        # Parse date strings if provided
        parsed_start_date = None
        parsed_end_date = None

        if start_date:
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

        if end_date:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

        # Validate date range
        if parsed_start_date and parsed_end_date and parsed_start_date > parsed_end_date:
            raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")

        # Validate pagination parameters
        if skip < 0:
            raise HTTPException(status_code=400, detail="skip must be a non-negative integer")
        if limit < 1:
            raise HTTPException(status_code=400, detail="limit must be a positive integer")
        if limit > 1000:
            raise HTTPException(status_code=400, detail="limit must not exceed 1000")

        # Get database models and total count - use date range if provided, otherwise use days
        if parsed_start_date and parsed_end_date:
            db_listings = await service.get_by_date_range(
                exchange_code, status, parsed_start_date, parsed_end_date, skip, limit
            )
            total = await service.get_by_date_range_count(
                exchange_code, status, parsed_start_date, parsed_end_date
            )
        else:
            db_listings = await service.get_filtered(exchange_code, status, days, skip, limit)
            total = await service.get_filtered_count(exchange_code, status, days)

        # Convert database models to Pydantic models to avoid detached session issues
        items = convert_db_listings_to_models(db_listings)

        # Return paginated response
        return PaginatedListings(
            items=items,
            total=total,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{symbol}", response_model=Listing)
async def get_listing(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Get listing by symbol.

    This endpoint retrieves a specific stock listing from the database by its symbol.

    Args:
        symbol (str): The symbol of the listing to retrieve.
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        Listing: The Listing object if found.

    Raises:
        HTTPException: If the listing is not found or if there's an error
                      retrieving the listing from the database.
    """
    service = ListingService(db)
    listing = await service.get_by_symbol(symbol)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Convert to Pydantic model to avoid detached session issues
    return convert_db_listing_to_model(listing)

@router.post("/", response_model=Listing)
async def create_listing(listing: ListingCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new listing.

    This endpoint creates a new stock listing in the database. If a listing with the
    same symbol and exchange code already exists, it updates the existing listing
    instead of creating a new one.

    Args:
        listing (ListingCreate): The listing data to create.
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        Listing: The created or updated Listing object.

    Raises:
        HTTPException: If there's an error creating or updating the listing in the database,
                      such as if the exchange with the given code doesn't exist.
    """
    service = ListingService(db)
    try:
        # Create in database
        db_listing = await service.create(listing)

        # Convert to Pydantic model to avoid detached session issues
        return convert_db_listing_to_model(db_listing)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 
