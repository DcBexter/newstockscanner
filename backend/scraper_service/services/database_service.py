"""Database service for the scraper service."""

import logging
from typing import Callable, Any, Awaitable, TypeVar
from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api_service.services import ListingService
from backend.core.models import ListingCreate
from backend.database.session import get_session_factory

logger = logging.getLogger(__name__)

T = TypeVar('T')

class DatabaseHelper:
    @staticmethod
    async def execute_db_operation(operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
        """Execute a database operation with proper session management."""
        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                result = await operation(session)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e

class DatabaseService:
    """Service for database operations related to stock listings."""
    
    def __init__(self):
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 5  # seconds
    
    @staticmethod
    async def save_listings(listings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save listings to the database using the ListingService."""
        if not listings:
            logger.info("No listings to save")
            return {"saved_count": 0, "total": 0, "new_listings": []}
            
        # Import the exchange service inside the method to avoid circular imports
        from backend.api_service.services.exchange_service import ExchangeService
        
        # Collect unique exchange codes to ensure they exist
        exchange_codes = set(
            listing.get("exchange_code") 
            for listing in listings 
            if listing.get("exchange_code")
        )
        
        # Cache for exchange data to avoid repeated database lookups
        exchange_data = {}
        
        # Step 1: Process exchanges first to ensure they exist in the database
        for exchange_code in exchange_codes:
            try:
                # Create a function to process this exchange
                async def process_exchange(db):
                    # Create a transaction
                    await db.begin()
                    
                    try:
                        # Look up the exchange
                        exchange_service = ExchangeService(db)
                        exchange = await exchange_service.get_by_code(exchange_code)
                        
                        # Create exchange if it doesn't exist
                        if not exchange:
                            if exchange_code == "NASDAQ":
                                exchange = await exchange_service.create_exchange({
                                    "name": "NASDAQ Stock Exchange",
                                    "code": "NASDAQ",
                                    "url": "https://www.nasdaq.com/"
                                })
                                logger.info(f"Created exchange: NASDAQ")
                            elif exchange_code == "NYSE":
                                exchange = await exchange_service.create_exchange({
                                    "name": "New York Stock Exchange",
                                    "code": "NYSE",
                                    "url": "https://www.nyse.com/"
                                })
                                logger.info(f"Created exchange: NYSE")
                            elif exchange_code == "HKEX":
                                exchange = await exchange_service.create_exchange({
                                    "name": "Hong Kong Stock Exchange",
                                    "code": "HKEX",
                                    "url": "https://www.hkex.com.hk/"
                                })
                                logger.info(f"Created exchange: HKEX")
                            elif exchange_code == "FSE":
                                exchange = await exchange_service.create_exchange({
                                    "name": "Frankfurt Stock Exchange",
                                    "code": "FSE",
                                    "url": "https://www.boerse-frankfurt.de/en",
                                    "description": "Frankfurt Stock Exchange (Börse Frankfurt)"
                                })
                                logger.info(f"Created exchange: FSE")
                        
                        # Cache exchange information
                        if exchange:
                            exchange_data[exchange_code] = {
                                "id": exchange.id,
                                "name": exchange.name,
                                "code": exchange.code,
                                "url": exchange.url
                            }
                        
                        # Commit the transaction
                        await db.commit()
                        return True
                    except Exception as e:
                        # Rollback transaction on error
                        await db.rollback()
                        logger.error(f"Error processing exchange {exchange_code}: {str(e)}")
                        return False
                
                # Execute the exchange processing with proper connection handling
                await DatabaseHelper.execute_db_operation(process_exchange)
                
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
                    
                    # Create service for listings
                    service = ListingService(db)
                    
                    # Now process each listing
                    for listing_data in listings:
                        try:
                            # Extract key fields for logging
                            symbol = listing_data.get('symbol', 'unknown')
                            exchange_code = listing_data.get('exchange_code', 'unknown')
                            
                            logger.debug(f"Processing listing: {symbol} ({exchange_code})")
                            
                            # Validate critical fields
                            if not symbol or len(symbol.strip()) == 0:
                                logger.warning(f"Skipping listing with empty symbol: {listing_data}")
                                continue
                                
                            if not exchange_code or len(exchange_code.strip()) == 0:
                                logger.warning(f"Skipping listing with empty exchange code: {listing_data}")
                                continue
                            
                            # Skip if we don't have exchange data
                            if exchange_code not in exchange_data:
                                logger.warning(f"Skipping listing with unknown exchange: {symbol} ({exchange_code})")
                                continue
                            
                            # Add exchange_id to data
                            listing_data["exchange_id"] = exchange_data[exchange_code]["id"]
                            
                            # Make sure exchange_code is included
                            if "exchange_code" not in listing_data and exchange_code:
                                listing_data["exchange_code"] = exchange_code
                            
                            # Check if listing exists
                            existing = await service.get_by_symbol_and_exchange(
                                symbol, exchange_code
                            )
                            
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
                                    listing_detail_url=listing_data.get("listing_detail_url")
                                )
                                
                                # Create the listing
                                await service.create(create_model)
                            
                            # Increment counter and track new listings
                            saved_count += 1
                            
                            if is_new:
                                new_listings.append(listing_data)
                                logger.info(f"New listing added: {symbol} ({exchange_code})")
                            else:
                                logger.debug(f"Updated existing listing: {symbol} ({exchange_code})")
                                
                        except Exception as e:
                            logger.warning(f"Failed to save listing {symbol}: {type(e).__name__}: {str(e)}")
                            continue
                    
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
            
            # Execute the listings processing with proper connection handling
            return await DatabaseHelper.execute_db_operation(process_listings)
            
        except Exception as e:
            logger.error(f"Error processing listings: {str(e)}")
            return {"saved_count": 0, "total": len(listings), "new_listings": []} 