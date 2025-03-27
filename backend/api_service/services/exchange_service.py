from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.cache import cache
from backend.core.exceptions import DatabaseCreateError, DatabaseDeleteError, DatabaseQueryError, DatabaseUpdateError
from backend.core.models import ExchangeCreate
from backend.database.models import Exchange


class ExchangeService:
    """Service for managing exchanges."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> List[Exchange]:
        """
        Get all exchanges.

        This method retrieves all exchanges from the database.
        Results are cached for 1 hour to improve performance since exchange data
        rarely changes.

        Returns:
            List[Exchange]: A list of all exchanges.

        Raises:
            DatabaseQueryError: If there's an error retrieving exchanges from the database.
        """
        try:
            # Check if the result is in the cache
            cache_key = "exchanges:all"
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # If not in cache, query the database
            query = select(Exchange)
            result = await self.db.execute(query)
            exchanges = list(result.scalars().all())

            # Cache the result for 1 hour (3600 seconds)
            cache.set(cache_key, exchanges, expire=3600)

            return exchanges
        except Exception as e:
            raise DatabaseQueryError(f"Failed to get exchanges: {str(e)}") from e

    async def get_by_code(self, code: str) -> Optional[Exchange]:
        """
        Get exchange by code.

        This method retrieves an exchange from the database by its code.
        Results are cached for 1 hour to improve performance since exchange data
        rarely changes.

        Args:
            code (str): The code of the exchange to retrieve.

        Returns:
            Optional[Exchange]: The exchange with the specified code, or None if not found.

        Raises:
            DatabaseQueryError: If there's an error retrieving the exchange from the database.
        """
        try:
            # Check if the result is in the cache
            cache_key = f"exchanges:code:{code}"
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # If not in cache, query the database
            query = select(Exchange).where(Exchange.code == code)
            result = await self.db.execute(query)
            exchange = result.scalar_one_or_none()

            # Cache the result for 1 hour (3600 seconds)
            # Only cache if the exchange was found
            if exchange is not None:
                cache.set(cache_key, exchange, expire=3600)

            return exchange
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
                name=exchange_data["name"], code=exchange_data["code"], url=exchange_data["url"], description=exchange_data.get("description", None)
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
                name=exchange_data["name"], code=exchange_data["code"], url=exchange_data["url"], description=exchange_data.get("description", None)
            )

            self.db.add(db_exchange)
            await self.db.commit()
            await self.db.refresh(db_exchange)

            # Invalidate the cache for all exchanges and this specific exchange
            cache.invalidate("exchanges:all")

            return db_exchange
        except Exception as e:
            await self.db.rollback()
            raise DatabaseCreateError(f"Failed to create exchange: {str(e)}", model="Exchange")

    async def update(self, code: str, exchange: ExchangeCreate) -> Optional[Exchange]:
        """
        Update an existing exchange.

        This method updates an existing exchange in the database.

        Args:
            code (str): The code of the exchange to update.
            exchange (ExchangeCreate): The new exchange data.

        Returns:
            Optional[Exchange]: The updated exchange, or None if the exchange doesn't exist.

        Raises:
            DatabaseUpdateError: If there's an error updating the exchange in the database.
        """
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

            # Invalidate the cache for all exchanges and this specific exchange
            cache.invalidate("exchanges:all")
            cache.invalidate(f"exchanges:code:{code}")

            # If the code was changed, also invalidate the cache for the new code
            if code != exchange.code:
                cache.invalidate(f"exchanges:code:{exchange.code}")

            return existing
        except Exception as e:
            await self.db.rollback()
            raise DatabaseUpdateError(f"Failed to update exchange: {str(e)}", model="Exchange") from e

    async def delete(self, code: str) -> bool:
        """
        Delete an exchange by its code.

        This method deletes an exchange from the database.

        Args:
            code (str): The code of the exchange to delete.

        Returns:
            bool: True if the exchange was deleted, False if the exchange doesn't exist.

        Raises:
            DatabaseDeleteError: If there's an error deleting the exchange from the database.
        """
        try:
            exchange = await self.get_by_code(code)
            if not exchange:
                return False

            await self.db.delete(exchange)
            await self.db.commit()

            # Invalidate the cache for all exchanges and this specific exchange
            cache.invalidate("exchanges:all")
            cache.invalidate(f"exchanges:code:{code}")

            return True
        except Exception as e:
            await self.db.rollback()
            raise DatabaseDeleteError(f"Failed to delete exchange: {str(e)}", model="Exchange", record_id=code) from e
