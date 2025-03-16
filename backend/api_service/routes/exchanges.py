"""
Routes for exchange operations.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Exchange, ExchangeCreate
from backend.database.session import get_db
from backend.api_service.services import ExchangeService

router = APIRouter(
    prefix="/exchanges",
    tags=["exchanges"],
)

@router.get("/", response_model=List[Exchange])
async def get_exchanges(db: AsyncSession = Depends(get_db)):
    """Get all exchanges."""
    service = ExchangeService(db)
    return await service.get_all()

@router.get("/{code}", response_model=Exchange)
async def get_exchange(code: str, db: AsyncSession = Depends(get_db)):
    """Get exchange by code."""
    service = ExchangeService(db)
    exchange = await service.get_by_code(code)
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not found")
    return exchange

@router.post("/", response_model=Exchange)
async def create_exchange(exchange: ExchangeCreate, db: AsyncSession = Depends(get_db)):
    """Create a new exchange."""
    service = ExchangeService(db)
    try:
        return await service.create(exchange)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 
