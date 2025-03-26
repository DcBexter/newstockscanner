"""
Service for managing stock listings in the database.

This module provides a service class for performing CRUD operations on stock listings,
including filtering, querying, and updating listings. It also includes functionality
for handling notifications about new listings.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, UTC
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.core.models import ListingCreate
from backend.database.models import StockListing, Exchange
from backend.core.exceptions import DatabaseError

class ListingService:
    """
    Service for managing stock listings in the database.

    This class provides methods for creating, retrieving, updating, and filtering
    stock listings in the database. It also includes functionality for handling
    notifications about new listings.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_filtered(
        self,
        exchange_code: Optional[str] = None,
        status: Optional[str] = None,
        days: Optional[int] = None
    ) -> List[StockListing]:
        """
        Get listings with filters.

        This method retrieves stock listings from the database with optional filters
        for exchange code, status, and time period.

        Args:
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
            status (Optional[str], optional): Filter by listing status. Defaults to None.
            days (Optional[int], optional): Get listings from the last N days. Defaults to None.

        Returns:
            List[StockListing]: A list of StockListing objects matching the filters.

        Raises:
            DatabaseError: If there's an error retrieving listings from the database.
        """
        try:
            # Use joinedload to eagerly load the exchange relationship
            query = select(StockListing).options(joinedload(StockListing.exchange)).join(Exchange)

            if exchange_code:
                query = query.where(Exchange.code == exchange_code)
            if status:
                query = query.where(StockListing.status == status)
            if days:
                # Calculate the date range
                since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
                query = query.where(StockListing.listing_date >= since)

            query = query.order_by(StockListing.listing_date.desc())

            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Failed to get listings: {str(e)}")

    async def get_by_symbol(self, symbol: str) -> Optional[StockListing]:
        """
        Get listing by symbol.

        This method retrieves a stock listing from the database by its symbol.

        Args:
            symbol (str): The symbol of the listing to retrieve.

        Returns:
            Optional[StockListing]: The StockListing object if found, None otherwise.

        Raises:
            DatabaseError: If there's an error retrieving the listing from the database.
        """
        try:
            # Use joinedload to eagerly load the exchange relationship
            query = select(StockListing).options(joinedload(StockListing.exchange)).where(StockListing.symbol == symbol)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError(f"Failed to get listing by symbol: {str(e)}")

    async def get_by_symbol_and_exchange(self, symbol: str, exchange_code: str) -> Optional[StockListing]:
        """
        Get listing by symbol and exchange code.

        This method retrieves a stock listing from the database by its symbol and exchange code.

        Args:
            symbol (str): The symbol of the listing to retrieve.
            exchange_code (str): The exchange code of the listing to retrieve.

        Returns:
            Optional[StockListing]: The StockListing object if found, None otherwise.

        Raises:
            DatabaseError: If there's an error retrieving the listing from the database.
        """
        try:
            # Use joinedload to eagerly load the exchange relationship
            query = select(StockListing).options(joinedload(StockListing.exchange)).join(Exchange).where(
                StockListing.symbol == symbol,
                Exchange.code == exchange_code
            )
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError(f"Failed to get listing by symbol and exchange: {str(e)}")

    async def update(self, listing_id: int, data: Dict[str, Any]) -> StockListing:
        """
        Update an existing listing.

        This method updates an existing stock listing in the database with the provided data.

        Args:
            listing_id (int): The ID of the listing to update.
            data (Dict[str, Any]): A dictionary containing the fields to update and their new values.

        Returns:
            StockListing: The updated StockListing object.

        Raises:
            DatabaseError: If there's an error updating the listing in the database,
                          or if the listing with the given ID doesn't exist.
        """
        try:
            # Get the existing listing
            query = select(StockListing).options(joinedload(StockListing.exchange)).where(StockListing.id == listing_id)
            result = await self.db.execute(query)
            listing = result.scalar_one_or_none()

            if not listing:
                raise DatabaseError(f"Listing with ID {listing_id} not found")

            # Update the listing fields
            for key, value in data.items():
                if key != "id" and hasattr(listing, key):
                    setattr(listing, key, value)

            # Save changes
            self.db.add(listing)
            await self.db.commit()
            await self.db.refresh(listing)

            # Ensure the exchange relationship is loaded
            await self.db.refresh(listing, ['exchange'])

            return listing
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Failed to update listing: {str(e)}")

    async def create(self, listing: ListingCreate) -> StockListing:
        """
        Create a new listing.

        This method creates a new stock listing in the database. If a listing with the
        same symbol and exchange code already exists, it updates the existing listing
        instead of creating a new one.

        Args:
            listing (ListingCreate): The listing data to create.

        Returns:
            StockListing: The created or updated StockListing object.

        Raises:
            DatabaseError: If there's an error creating or updating the listing in the database,
                          or if the exchange with the given code doesn't exist.
        """
        try:
            # Get exchange by code
            exchange = await self._get_exchange(listing.exchange_code)
            if not exchange:
                raise DatabaseError(f"Exchange with code {listing.exchange_code} not found")

            # Check if listing already exists
            existing = await self.get_by_symbol_and_exchange(listing.symbol, listing.exchange_code)
            if existing:
                # Update existing listing
                for attr, value in listing.model_dump().items():
                    if attr != "id" and hasattr(existing, attr):
                        setattr(existing, attr, value)

                self.db.add(existing)
                await self.db.commit()
                await self.db.refresh(existing)
                # Reload the exchange relationship
                await self.db.refresh(existing, ['exchange'])
                return existing

            # Create new listing with notified=False
            db_listing = self._create_listing_model(listing, exchange.id)
            db_listing.notified = False

            self.db.add(db_listing)
            await self.db.commit()
            await self.db.refresh(db_listing)
            # Ensure the exchange relationship is loaded
            db_listing.exchange = exchange

            return db_listing
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Failed to create listing: {str(e)}")

    async def _get_exchange(self, exchange_code: str) -> Optional[Exchange]:
        """
        Get exchange by code.

        This method retrieves an exchange from the database by its code.

        Args:
            exchange_code (str): The code of the exchange to retrieve.

        Returns:
            Optional[Exchange]: The Exchange object if found, None otherwise.
        """
        query = select(Exchange).where(Exchange.code == exchange_code)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _create_listing_model(self, listing: ListingCreate, exchange_id: int) -> StockListing:
        """
        Create a StockListing model from a ListingCreate model.

        This method creates a new StockListing object from a ListingCreate object
        and an exchange ID.

        Args:
            listing (ListingCreate): The listing data to create the model from.
            exchange_id (int): The ID of the exchange for the listing.

        Returns:
            StockListing: The created StockListing object.
        """
        return StockListing(
            name=listing.name,
            symbol=listing.symbol,
            listing_date=listing.listing_date,
            lot_size=listing.lot_size,
            status=listing.status,
            exchange_id=exchange_id,
            url=listing.url,
            security_type=listing.security_type,
            listing_detail_url=listing.listing_detail_url
        )

    async def get_unnotified_listings(self) -> List[StockListing]:
        """
        Get listings that haven't been notified yet.

        This method retrieves stock listings from the database that haven't been
        marked as notified yet.

        Returns:
            List[StockListing]: A list of StockListing objects that haven't been notified.

        Raises:
            DatabaseError: If there's an error retrieving listings from the database.
        """
        try:
            query = select(StockListing).options(joinedload(StockListing.exchange)).join(Exchange).where(
                StockListing.notified == False
            ).order_by(StockListing.created_at.desc())

            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Failed to get unnotified listings: {str(e)}")

    async def mark_as_notified(self, listing_id: int) -> bool:
        """
        Mark a listing as notified.

        This method marks a stock listing in the database as having been notified.

        Args:
            listing_id (int): The ID of the listing to mark as notified.

        Returns:
            bool: True if the listing was successfully marked as notified, False if the
                 listing with the given ID doesn't exist.

        Raises:
            DatabaseError: If there's an error updating the listing in the database.
        """
        try:
            query = select(StockListing).where(StockListing.id == listing_id)
            result = await self.db.execute(query)
            listing = result.scalar_one_or_none()

            if not listing:
                return False

            listing.notified = True
            self.db.add(listing)
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Failed to mark listing as notified: {str(e)}")

    async def get_by_date_range(
        self,
        exchange_code: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[StockListing]:
        """
        Get listings within a specific date range.

        This method retrieves stock listings from the database within a specific date range,
        with optional filters for exchange code and status.

        Args:
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
            status (Optional[str], optional): Filter by listing status. Defaults to None.
            start_date (Optional[datetime], optional): The start date of the range. Defaults to None.
            end_date (Optional[datetime], optional): The end date of the range. Defaults to None.

        Returns:
            List[StockListing]: A list of StockListing objects matching the filters and date range.

        Raises:
            DatabaseError: If there's an error retrieving listings from the database.
        """
        try:
            # Use joinedload to eagerly load the exchange relationship
            query = select(StockListing).options(joinedload(StockListing.exchange)).join(Exchange)

            if exchange_code:
                query = query.where(Exchange.code == exchange_code)
            if status:
                query = query.where(StockListing.status == status)

            # Apply date range filter
            if start_date:
                # Include the start date in the results (>=)
                query = query.where(StockListing.listing_date >= start_date)
            if end_date:
                # Include the end date in the results (<=)
                query = query.where(StockListing.listing_date <= end_date)

            # Default sort by listing date, most recent first
            query = query.order_by(StockListing.listing_date.desc())

            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Failed to get listings by date range: {str(e)}") 
