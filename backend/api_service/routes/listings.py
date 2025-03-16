"""
Routes for stock listing operations.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Listing, ListingCreate
from backend.database.session import get_db
from backend.api_service.services import ListingService

router = APIRouter(
    prefix="/listings",
    tags=["listings"],
)

@router.get("/", response_model=List[Listing])
async def get_listings(
    exchange_code: Optional[str] = None,
    status: Optional[str] = None,
    days: Optional[int] = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get listings with optional filters.
    
    Args:
        exchange_code: Filter by exchange code
        status: Filter by listing status
        days: Get listings from the last N days
        start_date: Get listings from this date (format: YYYY-MM-DD)
        end_date: Get listings up to this date (format: YYYY-MM-DD)
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
        
        # Get database models - use date range if provided, otherwise use days
        if parsed_start_date and parsed_end_date:
            db_listings = await service.get_by_date_range(
                exchange_code, status, parsed_start_date, parsed_end_date
            )
        else:
            db_listings = await service.get_filtered(exchange_code, status, days)
        
        # Convert database models to Pydantic models to avoid detached session issues
        return [
            Listing(
                id=listing.id,
                name=listing.name,
                symbol=listing.symbol,
                listing_date=listing.listing_date,
                lot_size=listing.lot_size,
                status=listing.status,
                exchange_code=listing.exchange.code,
                url=listing.url,
                security_type=listing.security_type,
                listing_detail_url=listing.listing_detail_url,
                created_at=listing.created_at,
                updated_at=listing.updated_at
            )
            for listing in db_listings
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{symbol}", response_model=Listing)
async def get_listing(symbol: str, db: AsyncSession = Depends(get_db)):
    """Get listing by symbol."""
    service = ListingService(db)
    listing = await service.get_by_symbol(symbol)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Convert to Pydantic model to avoid detached session issues
    return Listing(
        id=listing.id,
        name=listing.name,
        symbol=listing.symbol,
        listing_date=listing.listing_date,
        lot_size=listing.lot_size,
        status=listing.status,
        exchange_code=listing.exchange.code,
        url=listing.url,
        security_type=listing.security_type,
        listing_detail_url=listing.listing_detail_url,
        created_at=listing.created_at,
        updated_at=listing.updated_at
    )

@router.post("/", response_model=Listing)
async def create_listing(listing: ListingCreate, db: AsyncSession = Depends(get_db)):
    """Create a new listing."""
    service = ListingService(db)
    try:
        # Create in database
        db_listing = await service.create(listing)
        
        # Convert to Pydantic model to avoid detached session issues
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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 
