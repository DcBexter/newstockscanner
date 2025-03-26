from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import ExchangeCreate
from backend.database.models import Exchange
from backend.core.exceptions import DatabaseError, DatabaseQueryError, DatabaseCreateError, DatabaseUpdateError, DatabaseDeleteError

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
            raise DatabaseQueryError(f"Failed to get exchanges: {str(e)}") from e

    async def get_by_code(self, code: str) -> Optional[Exchange]:
        """Get exchange by code."""
        try:
            query = select(Exchange).where(Exchange.code == code)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseQueryError(f"Failed to get exchange by code: {str(e)}")

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
            raise DatabaseCreateError(f"Failed to create exchange: {str(e)}", model="Exchange")

    async def create(self, exchange: ExchangeCreate) -> Exchange:
        """
        Create a new exchange.

        This method creates a new exchange in the database. If an exchange with the
        same code already exists, it returns the existing exchange.

        Args:
            exchange (ExchangeCreate): The exchange data to create.

        Returns:
            Exchange: The created or existing Exchange object.

        Raises:
            DatabaseCreateError: If there's an error creating the exchange in the database.
        """
        try:
            # Check if exchange already exists
            existing = await self.get_by_code(exchange.code)
            if existing:
                return existing

            # Create new exchange using model_dump() to convert to dict
            exchange_data = exchange.model_dump()

            # Create new exchange
            db_exchange = Exchange(
                name=exchange_data["name"],
                code=exchange_data["code"],
                url=exchange_data["url"],
                description=exchange_data.get("description", None)
            )

            self.db.add(db_exchange)
            await self.db.commit()
            await self.db.refresh(db_exchange)

            return db_exchange
        except Exception as e:
            await self.db.rollback()
            raise DatabaseCreateError(f"Failed to create exchange: {str(e)}", model="Exchange")

    async def update(self, code: str, exchange: ExchangeCreate) -> Optional[Exchange]:
        """Update an existing exchange."""
        try:
            existing = await self.get_by_code(code)
            if not existing:
                return None

            # Update fields
            for attr, value in exchange.model_dump().items():
                if attr != "id" and hasattr(existing, attr):
                    setattr(existing, attr, value)

            self.db.add(existing)
            await self.db.commit()
            await self.db.refresh(existing)

            return existing
        except Exception as e:
            await self.db.rollback()
            raise DatabaseUpdateError(f"Failed to update exchange: {str(e)}", model="Exchange") from e

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
            raise DatabaseDeleteError(f"Failed to delete exchange: {str(e)}", model="Exchange", record_id=code) from e
