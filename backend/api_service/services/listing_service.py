"""
Service for managing stock listings in the database.

This module provides a service class for performing CRUD operations on stock listings,
including filtering, querying, and updating listings. It also includes functionality
for handling notifications about new listings.
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.core.exceptions import DatabaseQueryError, DatabaseNotFoundError, DatabaseUpdateError, DatabaseCreateError, \
    DatabaseTransactionError
from backend.core.models import ListingCreate
from backend.database.models import StockListing, Exchange


class ListingService:
    """
    Service for managing stock listings in the database.

    This class provides methods for creating, retrieving, updating, and filtering
    stock listings in the database. It also includes functionality for handling
    notifications about new listings.
    """

    # Constants for default values
    DEFAULT_DAYS = 30
    DEFAULT_SKIP = 0
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 1000  # Maximum limit to prevent excessive queries

    def __init__(self, db: AsyncSession):
        self.db = db

    def _create_select_query(self, select_obj, include_exchange_join: bool = True):
        """
        Create the initial select query.

        Args:
            select_obj: The SQLAlchemy select object (either StockListing or func.count(StockListing.id))
            include_exchange_join (bool, optional): Whether to include the join with Exchange. Defaults to True.

        Returns:
            The initial SQLAlchemy query object.
        """
        if isinstance(select_obj, type) and select_obj == StockListing:
            # If selecting StockListing entities, use joinedload for the exchange relationship
            query = select(select_obj).options(joinedload(StockListing.exchange))
        else:
            # If selecting a count or other expression, don't use joinedload
            query = select(select_obj)

        # Join with Exchange if needed
        if include_exchange_join:
            query = query.join(Exchange)

        return query

    def _apply_exchange_filter(self, query, exchange_code: Optional[str] = None):
        """
        Apply exchange code filter to the query.

        Args:
            query: The SQLAlchemy query object
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.

        Returns:
            The SQLAlchemy query object with exchange filter applied.
        """
        if exchange_code:
            query = query.where(Exchange.code == exchange_code)
        return query

    def _apply_status_filter(self, query, status: Optional[str] = None):
        """
        Apply status filter to the query.

        Args:
            query: The SQLAlchemy query object
            status (Optional[str], optional): Filter by listing status. Defaults to None.

        Returns:
            The SQLAlchemy query object with status filter applied.
        """
        if status:
            query = query.where(StockListing.status == status)
        return query

    def _apply_date_filters(
        self, 
        query, 
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """
        Apply date filters to the query.

        Args:
            query: The SQLAlchemy query object
            days (Optional[int], optional): Get listings from the last N days. Defaults to None.
            start_date (Optional[datetime], optional): The start date of the range. Defaults to None.
            end_date (Optional[datetime], optional): The end date of the range. Defaults to None.

        Returns:
            The SQLAlchemy query object with date filters applied.
        """
        # Apply date filters - either days or explicit date range
        if days:
            # Calculate the date range from days
            since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
            query = query.where(StockListing.listing_date >= since)
        else:
            # Apply explicit date range if provided
            if start_date:
                # Include the start date in the results (>=)
                query = query.where(StockListing.listing_date >= start_date)
            if end_date:
                # Include the end date in the results (<=)
                query = query.where(StockListing.listing_date <= end_date)

        return query

    def _build_base_query(
        self,
        select_obj,
        exchange_code: Optional[str] = None,
        status: Optional[str] = None,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_exchange_join: bool = True
    ):
        """
        Build a base query with common filters.

        This private method builds a base query with common filters that can be used
        by multiple public methods, reducing code duplication.

        Args:
            select_obj: The SQLAlchemy select object (either StockListing or func.count(StockListing.id))
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
            status (Optional[str], optional): Filter by listing status. Defaults to None.
            days (Optional[int], optional): Get listings from the last N days. Defaults to None.
            start_date (Optional[datetime], optional): The start date of the range. Defaults to None.
            end_date (Optional[datetime], optional): The end date of the range. Defaults to None.
            include_exchange_join (bool, optional): Whether to include the join with Exchange. Defaults to True.

        Returns:
            The SQLAlchemy query object with filters applied.
        """
        # Create the initial query
        query = self._create_select_query(select_obj, include_exchange_join)

        # Apply filters
        query = self._apply_exchange_filter(query, exchange_code)
        query = self._apply_status_filter(query, status)
        query = self._apply_date_filters(query, days, start_date, end_date)

        return query

    async def _get_listings_with_pagination(
        self,
        select_obj=StockListing,
        exchange_code: Optional[str] = None,
        status: Optional[str] = None,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = DEFAULT_SKIP,
        limit: int = DEFAULT_LIMIT,
        error_message: str = "Failed to get listings"
    ) -> List[StockListing]:
        """
        Get listings with filters and pagination.

        This is a helper method that handles the common logic of retrieving listings
        with pagination. It's used by both get_filtered and get_by_date_range.

        Args:
            select_obj: The SQLAlchemy select object (defaults to StockListing)
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
            status (Optional[str], optional): Filter by listing status. Defaults to None.
            days (Optional[int], optional): Get listings from the last N days. Defaults to None.
            start_date (Optional[datetime], optional): The start date of the range. Defaults to None.
            end_date (Optional[datetime], optional): The end date of the range. Defaults to None.
            skip (int, optional): Number of records to skip. Defaults to DEFAULT_SKIP.
            limit (int, optional): Maximum number of records to return. Defaults to DEFAULT_LIMIT.
            error_message (str, optional): Error message to use if an exception occurs. Defaults to "Failed to get listings".

        Returns:
            List[StockListing]: A list of StockListing objects matching the filters.

        Raises:
            DatabaseQueryError: If there's an error retrieving listings from the database.
        """
        # Log the query parameters
        filter_info = {
            "exchange_code": exchange_code,
            "status": status,
            "days": days,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "skip": skip,
            "limit": limit
        }
        logger = logging.getLogger(__name__)
        logger.debug(f"Getting listings with filters: {filter_info}")

        try:
            # Enforce maximum limit to prevent excessive queries
            original_limit = limit
            if limit > self.MAX_LIMIT:
                logger.warning(f"Requested limit {limit} exceeds maximum allowed {self.MAX_LIMIT}. Using maximum limit.")
                limit = self.MAX_LIMIT

            # Build the base query with filters
            query = self._build_base_query(
                select_obj,
                exchange_code=exchange_code,
                status=status,
                days=days,
                start_date=start_date,
                end_date=end_date
            )

            # Apply sorting
            query = query.order_by(StockListing.listing_date.desc())

            # Apply pagination
            query = query.offset(skip).limit(limit)

            # Execute the query
            result = await self.db.execute(query)
            listings = list(result.scalars().all())

            logger.debug(f"Retrieved {len(listings)} listings")
            return listings

        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "filters": filter_info
            }
            logger.error(f"{error_message}: {error_details}", exc_info=True)
            raise DatabaseQueryError(f"{error_message}: {str(e)}")

    async def _get_listings_count(
        self,
        exchange_code: Optional[str] = None,
        status: Optional[str] = None,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        error_message: str = "Failed to get listings count"
    ) -> int:
        """
        Get the total count of listings matching the filters.

        This is a helper method that handles the common logic of retrieving the count
        of listings. It's used by both get_filtered_count and get_by_date_range_count.

        Args:
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
            status (Optional[str], optional): Filter by listing status. Defaults to None.
            days (Optional[int], optional): Get listings from the last N days. Defaults to None.
            start_date (Optional[datetime], optional): The start date of the range. Defaults to None.
            end_date (Optional[datetime], optional): The end date of the range. Defaults to None.
            error_message (str, optional): Error message to use if an exception occurs. Defaults to "Failed to get listings count".

        Returns:
            int: The total count of listings matching the filters.

        Raises:
            DatabaseQueryError: If there's an error retrieving the count from the database.
        """
        # Log the query parameters
        filter_info = {
            "exchange_code": exchange_code,
            "status": status,
            "days": days,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
        logger = logging.getLogger(__name__)
        logger.debug(f"Getting listings count with filters: {filter_info}")

        try:
            # Build the count query using the base query helper
            query = self._build_base_query(
                func.count(StockListing.id),
                exchange_code=exchange_code,
                status=status,
                days=days,
                start_date=start_date,
                end_date=end_date
            )

            # Execute the query
            result = await self.db.execute(query)
            count = result.scalar() or 0

            logger.debug(f"Retrieved count: {count}")
            return count

        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "filters": filter_info
            }
            logger.error(f"{error_message}: {error_details}", exc_info=True)
            raise DatabaseQueryError(f"{error_message}: {str(e)}")

    async def get_filtered(
        self,
        exchange_code: Optional[str] = None,
        status: Optional[str] = None,
        days: Optional[int] = DEFAULT_DAYS,
        skip: int = DEFAULT_SKIP,
        limit: int = DEFAULT_LIMIT
    ) -> List[StockListing]:
        """
        Get listings with filters and pagination.

        This method retrieves stock listings from the database with optional filters
        for exchange code, status, and time period. It also supports pagination.

        Args:
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
            status (Optional[str], optional): Filter by listing status. Defaults to None.
            days (Optional[int], optional): Get listings from the last N days. Defaults to DEFAULT_DAYS.
            skip (int, optional): Number of records to skip. Defaults to DEFAULT_SKIP.
            limit (int, optional): Maximum number of records to return. Defaults to DEFAULT_LIMIT.

        Returns:
            List[StockListing]: A list of StockListing objects matching the filters.

        Raises:
            DatabaseError: If there's an error retrieving listings from the database.
        """
        return await self._get_listings_with_pagination(
            StockListing,
            exchange_code=exchange_code,
            status=status,
            days=days,
            skip=skip,
            limit=limit,
            error_message="Failed to get filtered listings"
        )

    async def get_filtered_count(
        self,
        exchange_code: Optional[str] = None,
        status: Optional[str] = None,
        days: Optional[int] = DEFAULT_DAYS
    ) -> int:
        """
        Get the total count of listings matching the filters.

        This method retrieves the total count of stock listings from the database
        that match the specified filters. This is useful for pagination UI.

        Args:
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
            status (Optional[str], optional): Filter by listing status. Defaults to None.
            days (Optional[int], optional): Get listings from the last N days. Defaults to DEFAULT_DAYS.

        Returns:
            int: The total count of listings matching the filters.

        Raises:
            DatabaseError: If there's an error retrieving the count from the database.
        """
        return await self._get_listings_count(
            exchange_code=exchange_code,
            status=status,
            days=days,
            error_message="Failed to get filtered listings count"
        )

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
            raise DatabaseQueryError(f"Failed to get listing by symbol: {str(e)}")

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
            raise DatabaseQueryError(f"Failed to get listing by symbol and exchange: {str(e)}")

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
                raise DatabaseNotFoundError(f"Listing with ID {listing_id} not found", model="StockListing", record_id=str(listing_id))

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
            raise DatabaseUpdateError(f"Failed to update listing: {str(e)}", model="StockListing")

    async def _update_existing_listing(self, existing: StockListing, listing: ListingCreate) -> StockListing:
        """
        Update an existing listing with new data.

        Args:
            existing (StockListing): The existing listing to update
            listing (ListingCreate): The new listing data

        Returns:
            StockListing: The updated listing

        Raises:
            DatabaseUpdateError: If there's an error updating the listing
        """
        try:
            # Update existing listing fields
            for attr, value in listing.model_dump().items():
                if attr != "id" and hasattr(existing, attr):
                    setattr(existing, attr, value)

            # Don't reset the notified flag if the listing has already been notified
            # This prevents re-notification of listings that have already been notified

            self.db.add(existing)
            await self.db.commit()
            await self.db.refresh(existing)

            # Reload the exchange relationship
            await self.db.refresh(existing, ['exchange'])

            return existing
        except Exception as e:
            await self.db.rollback()
            raise DatabaseUpdateError(f"Failed to update existing listing: {str(e)}", model="StockListing")

    async def _create_new_listing(self, listing: ListingCreate, exchange_id: int, exchange: Exchange) -> StockListing:
        """
        Create a new listing in the database.

        Args:
            listing (ListingCreate): The listing data to create
            exchange_id (int): The ID of the exchange for the listing
            exchange (Exchange): The exchange object to associate with the listing

        Returns:
            StockListing: The newly created listing

        Raises:
            DatabaseCreateError: If there's an error creating the listing
        """
        try:
            # Create new listing with notified=False
            db_listing = self._create_listing_model(listing, exchange_id)
            db_listing.notified = False

            self.db.add(db_listing)
            await self.db.commit()
            await self.db.refresh(db_listing)

            # Ensure the exchange relationship is loaded
            db_listing.exchange = exchange

            return db_listing
        except Exception as e:
            await self.db.rollback()
            raise DatabaseCreateError(f"Failed to create new listing: {str(e)}", model="StockListing")

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
                raise DatabaseNotFoundError(
                    f"Exchange with code {listing.exchange_code} not found", 
                    model="Exchange", 
                    record_id=listing.exchange_code
                )

            # Check if listing already exists
            existing = await self.get_by_symbol_and_exchange(listing.symbol, listing.exchange_code)

            if existing:
                # Update existing listing
                return await self._update_existing_listing(existing, listing)
            else:
                # Create new listing
                return await self._create_new_listing(listing, exchange.id, exchange)

        except (DatabaseUpdateError, DatabaseCreateError):
            # Re-raise specific database errors
            raise
        except Exception as e:
            # Catch any other exceptions
            await self.db.rollback()
            raise DatabaseCreateError(f"Failed to create listing: {str(e)}", model="StockListing")

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
            raise DatabaseQueryError(f"Failed to get unnotified listings: {str(e)}")

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
            raise DatabaseTransactionError(f"Failed to mark listing as notified: {str(e)}", operation="mark_as_notified")

    async def get_by_date_range(
        self,
        exchange_code: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = DEFAULT_SKIP,
        limit: int = DEFAULT_LIMIT
    ) -> List[StockListing]:
        """
        Get listings within a specific date range with pagination.

        This method retrieves stock listings from the database within a specific date range,
        with optional filters for exchange code and status. It also supports pagination.

        Args:
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
            status (Optional[str], optional): Filter by listing status. Defaults to None.
            start_date (Optional[datetime], optional): The start date of the range. Defaults to None.
            end_date (Optional[datetime], optional): The end date of the range. Defaults to None.
            skip (int, optional): Number of records to skip. Defaults to DEFAULT_SKIP.
            limit (int, optional): Maximum number of records to return. Defaults to DEFAULT_LIMIT.

        Returns:
            List[StockListing]: A list of StockListing objects matching the filters and date range.

        Raises:
            DatabaseError: If there's an error retrieving listings from the database.
        """
        return await self._get_listings_with_pagination(
            StockListing,
            exchange_code=exchange_code,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
            error_message="Failed to get listings by date range"
        )

    async def get_by_date_range_count(
        self,
        exchange_code: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """
        Get the total count of listings within a specific date range.

        This method retrieves the total count of stock listings from the database
        within a specific date range, with optional filters for exchange code and status.
        This is useful for pagination UI.

        Args:
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.
            status (Optional[str], optional): Filter by listing status. Defaults to None.
            start_date (Optional[datetime], optional): The start date of the range. Defaults to None.
            end_date (Optional[datetime], optional): The end date of the range. Defaults to None.

        Returns:
            int: The total count of listings matching the filters and date range.

        Raises:
            DatabaseError: If there's an error retrieving the count from the database.
        """
        return await self._get_listings_count(
            exchange_code=exchange_code,
            status=status,
            start_date=start_date,
            end_date=end_date,
            error_message="Failed to get listings count by date range"
        )
