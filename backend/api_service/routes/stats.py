"""
Routes for statistics operations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.api_service.services import StatsService

router = APIRouter(
    prefix="/statistics",
    tags=["statistics"],
)

@router.get("/")
async def get_listing_stats(
    days: int = 30,
    exchange_code: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Get listing statistics."""
    service = StatsService(db)
    try:
        return await service.get_listing_stats(days, exchange_code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 
