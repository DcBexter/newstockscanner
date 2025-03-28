"""Database service for the scraper service."""

import logging
from typing import Any, Awaitable, Callable, Dict, List, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api_service.services import ListingService
from backend.api_service.services.exchange_service import ExchangeService
from backend.config.exchange_config import get_exchange_data
from backend.core.models import ListingCreate
from backend.database.session import get_session_factory

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DatabaseHelper:
    """Helper class for database operations with proper session management."""

    def __init__(self, session_factory=None):
        """
        Initialize the DatabaseHelper with a session factory.

        Args:
            session_factory: A callable that returns an AsyncSession when called.
                            If None, the default session factory will be used.
        """
        self.session_factory = session_factory or get_session_factory()

    async def execute_db_operation(self, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
        """
        Execute a database operation with proper session management.

        Args:
            operation: A callable that takes an AsyncSession and returns an awaitable.

        Returns:
            The result of the operation.

        Raises:
            Any exception raised by the operation.
        """
        async with self.session_factory() as session:
            try:
                result = await operation(session)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e


class DatabaseService:
    """Service for database operations related to stock listings."""

    def __init__(self, db_helper=None, session_factory=None, exchange_service_factory=None, listing_service_factory=None):
        """
        Initialize the DatabaseService with dependencies.

        Args:
            db_helper: A DatabaseHelper instance for database operations.
                      If None, a new instance will be created.
            session_factory: A callable that returns an AsyncSession when called.
                            If None, the default session factory will be used.
            exchange_service_factory: A callable that takes an AsyncSession and returns an ExchangeService.
                                     If None, a default factory will be used.
            listing_service_factory: A callable that takes an AsyncSession and returns a ListingService.
                                    If None, a default factory will be used.
        """
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 5  # seconds

        # Set up dependencies with defaults if not provided
        self.session_factory = session_factory or get_session_factory()
        self.db_helper = db_helper or DatabaseHelper(self.session_factory)

        # Default factories create new instances of the services
        self.exchange_service_factory = exchange_service_factory or (lambda db: ExchangeService(db))
        self.listing_service_factory = listing_service_factory or (lambda db: ListingService(db))

    @staticmethod
    def _get_exchange_creation_data(exchange_code: str) -> Dict[str, Any]:
        """Return the data needed to create an exchange based on its code."""
        return get_exchange_data(exchange_code)

    async def _process_single_exchange(self, db: AsyncSession, exchange_code: str) -> Dict[str, Any]:
        """Process a single exchange - look it up or create it if it doesn't exist."""
        try:
            # Create a transaction
            await db.begin()

            try:
                # Look up the exchange using the injected factory
                exchange_service = self.exchange_service_factory(db)
                exchange = await exchange_service.get_by_code(exchange_code)

                # Create exchange if it doesn't exist
                if not exchange:
                    exchange_data = self._get_exchange_creation_data(exchange_code)
                    if exchange_data:
                        exchange = await exchange_service.create_exchange(exchange_data)
                        logger.info(f"Created exchange: {exchange_code}")
                    else:
                        logger.warning(f"No data available to create exchange: {exchange_code}")
                        return None

                # Return exchange information
                if exchange:
                    result = {"id": exchange.id, "name": exchange.name, "code": exchange.code, "url": exchange.url}

                    # Commit the transaction
                    await db.commit()
                    return result
                return None
            except Exception as e:
                # Rollback transaction on error
                await db.rollback()
                logger.error(f"Error processing exchange {exchange_code}: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"Transaction setup error for exchange {exchange_code}: {str(e)}")
            return None

    async def _process_single_listing(
        self, db: AsyncSession, listing_data: Dict[str, Any], exchange_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process a single listing - validate, create or update it."""
        try:
            # Extract key fields for logging
            symbol = listing_data.get("symbol", "unknown")
            exchange_code = listing_data.get("exchange_code", "unknown")

            logger.debug(f"Processing listing: {symbol} ({exchange_code})")

            # Validate critical fields
            if not symbol or len(symbol.strip()) == 0:
                logger.warning(f"Skipping listing with empty symbol: {listing_data}")
                return {"success": False, "reason": "empty_symbol"}

            if not exchange_code or len(exchange_code.strip()) == 0:
                logger.warning(f"Skipping listing with empty exchange code: {listing_data}")
                return {"success": False, "reason": "empty_exchange_code"}

            # Skip if we don't have exchange data
            if exchange_code not in exchange_data:
                logger.warning(f"Skipping listing with unknown exchange: {symbol} ({exchange_code})")
                return {"success": False, "reason": "unknown_exchange"}

            # Add exchange_id to data
            listing_data["exchange_id"] = exchange_data[exchange_code]["id"]

            # Make sure exchange_code is included
            if "exchange_code" not in listing_data and exchange_code:
                listing_data["exchange_code"] = exchange_code

            # Create service for listings using the injected factory
            service = self.listing_service_factory(db)

            # Check if listing exists
            existing = await service.get_by_symbol_and_exchange(symbol, exchange_code)

            # Determine if this is a new listing or an update
            is_new = False

            if existing:
                # Update existing listing
                listing_data["id"] = existing.id
                await service.update(existing.id, listing_data)
            else:
                # Create new listing
                is_new = True

                # Convert to a proper create model
                create_model = ListingCreate(
                    name=listing_data.get("name", ""),
                    symbol=listing_data.get("symbol", ""),
                    listing_date=listing_data.get("listing_date"),
                    lot_size=listing_data.get("lot_size", 0),
                    status=listing_data.get("status", ""),
                    exchange_id=listing_data.get("exchange_id"),
                    exchange_code=listing_data.get("exchange_code", ""),
                    security_type=listing_data.get("security_type", "Equity"),
                    url=listing_data.get("url"),
                    listing_detail_url=listing_data.get("listing_detail_url"),
                )

                # Create the listing
                await service.create(create_model)

            # Return result
            result = {"success": True, "is_new": is_new, "symbol": symbol, "exchange_code": exchange_code, "data": listing_data}

            if is_new:
                logger.info(f"New listing added: {symbol} ({exchange_code})")
            else:
                logger.debug(f"Updated existing listing: {symbol} ({exchange_code})")

            return result

        except Exception as e:
            logger.warning(f"Failed to save listing {listing_data.get('symbol', 'unknown')}: {type(e).__name__}: {str(e)}")
            return {"success": False, "reason": "exception", "error": str(e)}

    async def save_listings(self, listings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save listings to the database using the ListingService.

        Args:
            listings: A list of listing data dictionaries to save.

        Returns:
            A dictionary with the results of the operation, including:
            - saved_count: The number of listings successfully saved
            - total: The total number of listings processed
            - new_listings: A list of newly created listings
        """
        if not listings:
            logger.info("No listings to save")
            return {"saved_count": 0, "total": 0, "new_listings": []}

        # Collect unique exchange codes to ensure they exist
        exchange_codes = set(listing.get("exchange_code") for listing in listings if listing.get("exchange_code"))

        # Cache for exchange data to avoid repeated database lookups
        exchange_data = {}

        # Step 1: Process exchanges first to ensure they exist in the database
        for exchange_code in exchange_codes:
            try:
                # Process this exchange using the helper method
                async def process_exchange_wrapper(db):
                    exchange_info = await self._process_single_exchange(db, exchange_code)
                    if exchange_info:
                        exchange_data[exchange_code] = exchange_info
                    return exchange_info

                # Execute the exchange processing with proper connection handling
                await self.db_helper.execute_db_operation(process_exchange_wrapper)

            except Exception as e:
                logger.error(f"Error setting up exchange {exchange_code}: {str(e)}")

        # Step 2: Process all listings in a single transaction
        try:
            # Define a function to process all listings
            async def process_listings(db):
                saved_count = 0
                new_listings = []

                try:
                    # Start a transaction
                    await db.begin()

                    # Now process each listing
                    for listing_data in listings:
                        # Process this listing using the helper method
                        result = await self._process_single_listing(db, listing_data, exchange_data)

                        # Check if the listing was processed successfully
                        if result.get("success"):
                            saved_count += 1

                            # Track new listings
                            if result.get("is_new"):
                                new_listings.append(result.get("data"))

                    # Commit the transaction
                    await db.commit()

                    logger.info(f"Successfully saved {saved_count} out of {len(listings)} listings to the database")
                    logger.info(f"Found {len(new_listings)} new listings that weren't in the database before")

                    return {"saved_count": saved_count, "total": len(listings), "new_listings": new_listings}

                except Exception as e:
                    # Ensure transaction is rolled back
                    await db.rollback()
                    logger.error(f"Transaction error: {type(e).__name__}: {str(e)}")
                    # Return empty results if database error occurs
                    return {"saved_count": 0, "total": len(listings), "new_listings": []}

            # Execute the listings processing with proper connection handling
            return await self.db_helper.execute_db_operation(process_listings)

        except Exception as e:
            logger.error(f"Error processing listings: {str(e)}")
            return {"saved_count": 0, "total": len(listings), "new_listings": []}
