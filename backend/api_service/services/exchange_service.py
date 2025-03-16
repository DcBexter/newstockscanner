from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import ExchangeCreate
from backend.database.models import Exchange
from backend.core.exceptions import DatabaseError

class ExchangeService:
    """Service for managing exchanges."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> List[Exchange]:
        """Get all exchanges."""
        try:
            query = select(Exchange)
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Failed to get exchanges: {str(e)}") from e

    async def get_by_code(self, code: str) -> Optional[Exchange]:
        """Get exchange by code."""
        try:
            query = select(Exchange).where(Exchange.code == code)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError(f"Failed to get exchange by code: {str(e)}")

    async def create_exchange(self, exchange_data: Dict[str, Any]) -> Exchange:
        """Create a new exchange."""
        try:
            # Check if exchange already exists
            existing = await self.get_by_code(exchange_data["code"])
            if existing:
                return existing
            
            # Create new exchange
            exchange = Exchange(
                name=exchange_data["name"],
                code=exchange_data["code"],
                url=exchange_data["url"],
                description=exchange_data.get("description", None)
            )
            
            self.db.add(exchange)
            await self.db.commit()
            await self.db.refresh(exchange)
            
            return exchange
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Failed to create exchange: {str(e)}")

    async def update(self, code: str, exchange: ExchangeCreate) -> Optional[Exchange]:
        """Update an existing exchange."""
        try:
            existing = await self.get_by_code(code)
            if not existing:
                return None
            
            # Update fields
            for attr, value in exchange.dict().items():
                if attr != "id" and hasattr(existing, attr):
                    setattr(existing, attr, value)
            
            self.db.add(existing)
            await self.db.commit()
            await self.db.refresh(existing)
            
            return existing
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Failed to update exchange: {str(e)}") from e

    async def delete(self, code: str) -> bool:
        """Delete an exchange by its code."""
        try:
            exchange = await self.get_by_code(code)
            if not exchange:
                return False
            
            await self.db.delete(exchange)
            await self.db.commit()
            
            return True
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Failed to delete exchange: {str(e)}") from e 
