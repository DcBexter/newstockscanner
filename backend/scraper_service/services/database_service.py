"""Database service for the scraper service."""

import logging
from typing import Callable, Any, Awaitable, TypeVar
from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api_service.services import ListingService
from backend.api_service.services.exchange_service import ExchangeService
from backend.config.exchange_config import get_exchange_data
from backend.core.models import ListingCreate
from backend.database.session import get_session_factory

logger = logging.getLogger(__name__)

T = TypeVar('T')

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

    def __init__(self, 
                 db_helper=None, 
                 session_factory=None,
                 exchange_service_factory=None,
                 listing_service_factory=None):
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
        """
        Process a single exchange - look it up or create it if it doesn't exist.

        Args:
            db: Database session
            exchange_code: The code of the exchange to process

        Returns:
            A dictionary with the exchange information if successful, or error information if failed
        """
        try:
            # Create a transaction
            await db.begin()

            # Look up the exchange using the injected factory
            exchange_service = self.exchange_service_factory(db)
            exchange = await exchange_service.get_by_code(exchange_code)

            # Create exchange if it doesn't exist
            if not exchange:
                exchange_data = self._get_exchange_creation_data(exchange_code)
                if not exchange_data:
                    logger.warning(f"No data available to create exchange: {exchange_code}")
                    await db.rollback()
                    return {
                        "success": False,
                        "reason": "missing_exchange_data",
                        "exchange_code": exchange_code
                    }

                exchange = await exchange_service.create_exchange(exchange_data)
                logger.info(f"Created exchange: {exchange_code}")

            # Verify exchange was found or created
            if not exchange:
                logger.warning(f"Failed to find or create exchange: {exchange_code}")
                await db.rollback()
                return {
                    "success": False,
                    "reason": "exchange_not_found",
                    "exchange_code": exchange_code
                }

            # Create result with exchange information
            result = {
                "success": True,
                "id": exchange.id,
                "name": exchange.name,
                "code": exchange.code,
                "url": exchange.url
            }

            # Commit the transaction
            await db.commit()
            return result

        except Exception as e:
            # Ensure transaction is rolled back
            try:
                await db.rollback()
            except Exception as rollback_error:
                logger.error(f"Error during rollback for exchange {exchange_code}: {str(rollback_error)}")

            error_type = type(e).__name__
            error_msg = str(e)
            logger.error(f"Error processing exchange {exchange_code}: {error_type}: {error_msg}")

            return {
                "success": False,
                "reason": "exception",
                "exchange_code": exchange_code,
                "error_type": error_type,
                "error": error_msg
            }

    @staticmethod
    def _validate_listing_data(listing_data: Dict[str, Any], exchange_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate listing data and return validation result.

        Args:
            listing_data: The listing data to validate
            exchange_data: Dictionary of exchange data keyed by exchange code

        Returns:
            Dict with validation result. If validation fails, contains success=False and reason.
        """
        # Extract key fields for logging
        symbol = listing_data.get('symbol', 'unknown')
        exchange_code = listing_data.get('exchange_code', 'unknown')

        logger.debug(f"Validating listing: {symbol} ({exchange_code})")

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

        return {"success": True, "symbol": symbol, "exchange_code": exchange_code}

    @staticmethod
    def _prepare_listing_data(listing_data: Dict[str, Any], validation_result: Dict[str, Any],
                              exchange_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Prepare listing data for database operations.

        Args:
            listing_data: The original listing data
            validation_result: The result from validation
            exchange_data: Dictionary of exchange data keyed by exchange code

        Returns:
            Dict with prepared listing data
        """
        # Create a copy to avoid modifying the original
        prepared_data = listing_data.copy()

        exchange_code = validation_result["exchange_code"]

        # Add exchange_id to data
        prepared_data["exchange_id"] = exchange_data[exchange_code]["id"]

        # Make sure exchange_code is included
        if "exchange_code" not in prepared_data and exchange_code:
            prepared_data["exchange_code"] = exchange_code

        return prepared_data

    async def _create_or_update_listing(self, db: AsyncSession, prepared_data: Dict[str, Any], 
                                       validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new listing or update an existing one.

        Args:
            db: Database session
            prepared_data: Prepared listing data
            validation_result: The result from validation

        Returns:
            Dict with operation result including is_new flag
        """
        symbol = validation_result["symbol"]
        exchange_code = validation_result["exchange_code"]

        # Create service for listings using the injected factory
        service = self.listing_service_factory(db)

        # Check if listing exists
        existing = await service.get_by_symbol_and_exchange(
            symbol, exchange_code
        )

        # Determine if this is a new listing or an update
        is_new = False

        if existing:
            # Update existing listing
            prepared_data["id"] = existing.id
            await service.update(existing.id, prepared_data)
        else:
            # Create new listing
            is_new = True

            # Convert to a proper create model
            create_model = ListingCreate(
                name=prepared_data.get("name", ""),
                symbol=prepared_data.get("symbol", ""),
                listing_date=prepared_data.get("listing_date"),
                lot_size=prepared_data.get("lot_size", 0),
                status=prepared_data.get("status", ""),
                exchange_id=prepared_data.get("exchange_id"),
                exchange_code=prepared_data.get("exchange_code", ""),
                security_type=prepared_data.get("security_type", "Equity"),
                url=prepared_data.get("url"),
                listing_detail_url=prepared_data.get("listing_detail_url")
            )

            # Create the listing
            await service.create(create_model)

        return {"is_new": is_new, "data": prepared_data}

    @staticmethod
    def _create_listing_result(operation_result: Dict[str, Any], validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create the final result object for the listing operation.

        Args:
            operation_result: Result from create/update operation
            validation_result: Result from validation

        Returns:
            Dict with final operation result
        """
        symbol = validation_result["symbol"]
        exchange_code = validation_result["exchange_code"]
        is_new = operation_result["is_new"]

        # Create result object
        result = {
            "success": True,
            "is_new": is_new,
            "symbol": symbol,
            "exchange_code": exchange_code,
            "data": operation_result["data"]
        }

        # Log appropriate message
        if is_new:
            logger.info(f"New listing added: {symbol} ({exchange_code})")
        else:
            logger.debug(f"Updated existing listing: {symbol} ({exchange_code})")

        return result

    async def _process_single_listing(
        self,
        db: AsyncSession, 
        listing_data: Dict[str, Any], 
        exchange_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process a single listing - validate, create or update it."""
        try:
            # Step 1: Validate the listing data
            validation_result = self._validate_listing_data(listing_data, exchange_data)
            if not validation_result["success"]:
                return validation_result

            # Step 2: Prepare the listing data
            prepared_data = self._prepare_listing_data(listing_data, validation_result, exchange_data)

            # Step 3: Create or update the listing
            operation_result = await self._create_or_update_listing(db, prepared_data, validation_result)

            # Step 4: Create and return the result
            return self._create_listing_result(operation_result, validation_result)

        except Exception as e:
            logger.warning(f"Failed to save listing {listing_data.get('symbol', 'unknown')}: {type(e).__name__}: {str(e)}")
            return {"success": False, "reason": "exception", "error": str(e)}


    @staticmethod
    def _collect_exchange_codes(listings: List[Dict[str, Any]]) -> set:
        """
        Collect unique exchange codes from listings.

        Args:
            listings: A list of listing data dictionaries

        Returns:
            A set of unique exchange codes
        """
        return set(
            listing.get("exchange_code") 
            for listing in listings 
            if listing.get("exchange_code")
        )

    async def _process_exchanges(self, exchange_codes: set) -> Dict[str, Dict[str, Any]]:
        """
        Process exchanges to ensure they exist in the database.

        Args:
            exchange_codes: A set of exchange codes to process

        Returns:
            A dictionary of exchange data keyed by exchange code
        """
        exchange_data = {}
        failed_exchanges = []

        for exchange_code in exchange_codes:
            try:
                # Define a wrapper function to process the exchange
                async def process_exchange_wrapper(db):
                    return await self._process_single_exchange(db, exchange_code)

                # Execute the exchange processing with proper connection handling
                result = await self.db_helper.execute_db_operation(process_exchange_wrapper)

                # Store the exchange info if it was processed successfully
                if result and result.get("success", False):
                    # Remove the success flag before storing
                    exchange_info = {k: v for k, v in result.items() if k != "success"}
                    exchange_data[exchange_code] = exchange_info
                else:
                    # Log the failure reason
                    reason = result.get("reason", "unknown") if result else "no_result"
                    logger.warning(f"Failed to process exchange {exchange_code}: {reason}")
                    failed_exchanges.append(exchange_code)

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                logger.error(f"Error setting up exchange {exchange_code}: {error_type}: {error_msg}")
                failed_exchanges.append(exchange_code)

        if failed_exchanges:
            logger.warning(f"Failed to process {len(failed_exchanges)} exchanges: {', '.join(failed_exchanges)}")

        return exchange_data

    async def _process_listings_transaction(self, db: AsyncSession, listings: List[Dict[str, Any]], 
                                          exchange_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process all listings in a single transaction.

        Args:
            db: Database session
            listings: A list of listing data dictionaries
            exchange_data: Dictionary of exchange data keyed by exchange code

        Returns:
            A dictionary with the results of the operation
        """
        saved_count = 0
        new_listings = []

        try:
            # Start a transaction
            await db.begin()

            # Process each listing
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

            return {
                "saved_count": saved_count, 
                "total": len(listings),
                "new_listings": new_listings
            }

        except Exception as e:
            # Ensure transaction is rolled back
            await db.rollback()
            logger.error(f"Transaction error: {type(e).__name__}: {str(e)}")
            # Return empty results if database error occurs
            return {"saved_count": 0, "total": len(listings), "new_listings": []}

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

        try:
            # Step 1: Collect unique exchange codes
            exchange_codes = self._collect_exchange_codes(listings)

            # Step 2: Process exchanges to ensure they exist in the database
            exchange_data = await self._process_exchanges(exchange_codes)

            # Step 3: Process all listings in a single transaction
            async def process_listings_wrapper(db):
                return await self._process_listings_transaction(db, listings, exchange_data)

            # Execute the listings processing with proper connection handling
            return await self.db_helper.execute_db_operation(process_listings_wrapper)

        except Exception as e:
            logger.error(f"Error processing listings: {str(e)}")
            return {"saved_count": 0, "total": len(listings), "new_listings": []}
