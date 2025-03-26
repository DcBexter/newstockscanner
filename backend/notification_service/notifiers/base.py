import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, TYPE_CHECKING, List, Dict, Any

import aiohttp
from aiohttp import ClientTimeout

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.log_config import get_logger
from backend.config.settings import get_settings
from backend.core.exceptions import NotifierError
from backend.core.models import NotificationMessage

settings = get_settings()
logger = get_logger(__name__)

class BaseNotifier(ABC):
    """Base class for all notifiers."""
    # Constants for message handling
    MAX_MESSAGE_LENGTH = 4000  # Default maximum message length
    LISTINGS_PER_MESSAGE = 10  # Default number of listings per message
    MAX_RETRIES = 3  # Default maximum number of retries
    RETRY_DELAY = 5  # Default delay between retries in seconds
    MESSAGE_DELAY = 1  # Default delay between messages in seconds

    def __init__(self, db: Optional["AsyncSession"] = None):
        self.settings = settings
        self.logger = logger
        self.db = db
        self._session: Optional[aiohttp.ClientSession] = None

    @abstractmethod
    async def send_single_message(self, message: NotificationMessage) -> bool:
        """
        Send a single notification message.

        This is the only method that subclasses must implement.
        It should handle the actual sending of a message to the notification service.

        Args:
            message: The notification message to send.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        pass

    async def send(self, message: NotificationMessage) -> bool:
        """
        Send a notification message.

        This method handles formatting the message and splitting it into multiple parts if necessary.
        Subclasses should not override this method, but instead implement send_single_message.

        Args:
            message: The notification message to send.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        try:
            # Format the message
            formatted_message = await self.format_message(message)

            # Check if message exceeds maximum length
            if len(formatted_message) > self.MAX_MESSAGE_LENGTH:
                self.logger.info(f"Message exceeds maximum length ({len(formatted_message)} > {self.MAX_MESSAGE_LENGTH}). Splitting into multiple messages.")
                return await self._send_long_message(message, formatted_message)

            # Send the message
            return await self.send_single_message(message)
        except Exception as exception:
            self.logger.error(f"Error sending message: {str(exception)}")
            return False

    async def initialize(self) -> None:
        """Initialize the notifier with necessary setup.

        This method creates an aiohttp.ClientSession that can be used by subclasses.
        Subclasses should call super().initialize() before doing their own initialization.
        """
        if self._session is None:
            timeout = ClientTimeout(total=30)  # Default timeout of 30 seconds
            self._session = aiohttp.ClientSession(timeout=timeout)
            self.logger.debug("Created aiohttp.ClientSession in BaseNotifier.initialize()")

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get the aiohttp.ClientSession.

        Raises:
            RuntimeError: If the session is not initialized.
        """
        if not self._session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager or call initialize() first.")
        return self._session

    @staticmethod
    async def format_message(message: NotificationMessage) -> str:
        """Format the notification message."""
        try:
            metadata_str = ""
            if message.metadata:
                metadata_str = "\n\nMetadata:\n" + "\n".join(
                    f"- {k}: {v}" for k, v in message.metadata.items()
                )

            return (
                f"{message.title}\n"
                f"---\n"
                f"{message.body}"
                f"{metadata_str}\n"
                f"\nTimestamp: {message.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        except Exception as exception:
            raise NotifierError(f"Failed to format message: {str(exception)}") from exception

    async def _send_long_message(self, message: NotificationMessage, formatted_message: str) -> bool:
        """
        Split a long message into multiple parts and send each part.

        Args:
            message: The original notification message
            formatted_message: The formatted message text that exceeds the maximum length

        Returns:
            bool: True if all parts were sent successfully, False otherwise
        """
        # Split the message at natural boundaries (double newlines between listings)
        parts = []

        # If the message contains listings (separated by double newlines)
        if "\n\n" in formatted_message:
            sections = formatted_message.split("\n\n")
            header = sections[0] + "\n\n"  # Keep the header in all parts

            current_part = header
            for section in sections[1:]:  # Skip the header which we already added
                # If adding this section would exceed the limit, start a new part
                if len(current_part + section + "\n\n") > self.MAX_MESSAGE_LENGTH:
                    parts.append(current_part.rstrip())
                    current_part = header + section + "\n\n"
                else:
                    current_part += section + "\n\n"

            # Add the last part if it's not empty
            if current_part and current_part != header:
                parts.append(current_part.rstrip())
        else:
            # If there are no natural boundaries, split by character count
            for char_index in range(0, len(formatted_message), self.MAX_MESSAGE_LENGTH):
                parts.append(formatted_message[char_index:char_index + self.MAX_MESSAGE_LENGTH])

        # Send each part
        all_success = True
        for part_index, part in enumerate(parts):
            part_message = NotificationMessage(
                title=f"{message.title} (Part {part_index+1}/{len(parts)})",
                body=part,
                metadata={
                    **message.metadata,
                    "part": part_index+1,
                    "total_parts": len(parts)
                }
            )

            success = await self.send_single_message(part_message)
            if not success:
                self.logger.error(f"Failed to send part {part_index+1}/{len(parts)} of long message")
                all_success = False

            # Add a small delay between messages to avoid rate limiting
            if part_index < len(parts) - 1:
                await asyncio.sleep(self.MESSAGE_DELAY)

        return all_success

    def _deduplicate_listings(self, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate listings based on symbol, exchange_code, and ID (if available).

        Args:
            listings: A list of listing dictionaries to deduplicate.

        Returns:
            A list of deduplicated listings.
        """
        unique_listings = {}
        for listing in listings:
            # Create a unique key for each listing
            if 'id' in listing:
                key = f"{listing['exchange_code']}_{listing['symbol']}_{listing['id']}"
            else:
                key = f"{listing['exchange_code']}_{listing['symbol']}"
            unique_listings[key] = listing

        deduplicated_listings = list(unique_listings.values())
        self.logger.info(f"Deduplicated {len(listings)} listings to {len(deduplicated_listings)} unique entries")
        return deduplicated_listings

    @staticmethod
    def _group_listings_by_exchange(listings: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group listings by exchange code.

        Args:
            listings: A list of listing dictionaries to group.

        Returns:
            A dictionary mapping exchange codes to lists of listings.
        """
        listings_by_exchange = {}
        for listing in listings:
            exchange_code = listing['exchange_code']
            if exchange_code not in listings_by_exchange:
                listings_by_exchange[exchange_code] = []
            listings_by_exchange[exchange_code].append(listing)
        return listings_by_exchange



    @staticmethod
    async def format_listing(listing: Dict[str, Any]) -> str:
        """
        Format a single listing into a human-readable message.

        Args:
            listing: A dictionary containing listing data.

        Returns:
            A formatted message string for the listing.
        """
        # Convert listing date to datetime if it's a string
        listing_date = listing['listing_date']
        if isinstance(listing_date, str):
            listing_date = datetime.fromisoformat(listing_date)

        name = listing['name']
        symbol = listing['symbol']
        status = listing['status']
        security_type = listing['security_type']

        # Format stock info with URL if available
        primary_url = listing.get('url')
        stock_info = f"<a href='{primary_url}'>{symbol}</a>" if primary_url else symbol

        # Build the listing body
        listing_body = (
            f"<b>{name}</b> ({stock_info})\n"
            f"📅 Listing Date: {listing_date.strftime('%Y-%m-%d')}\n"
            f"📊 Lot Size: {listing['lot_size']:,}\n"
            f"📝 Status: {status}\n"
            f"🔖 Type: {security_type}\n"
        )

        # Only add detail link if URL exists and is not None
        if listing.get('listing_detail_url'):
            listing_body += f"🌐 <a href='{listing['listing_detail_url']}'>View Details</a>\n"

        return listing_body

    async def _send_exchange_listings(self, exchange: str, exchange_listings: List[Dict[str, Any]], 
                                     all_exchanges: List[str]) -> None:
        """
        Send listings for a specific exchange.

        Args:
            exchange: The exchange code.
            exchange_listings: A list of listings for the exchange.
            all_exchanges: A list of all exchange codes (used for determining if this is the last exchange).
        """
        # Sort listings by listing date (newest first)
        def get_listing_date(exchange_listing):
            """Convert listing date to datetime if it's a string."""
            date = exchange_listing['listing_date']
            return date if isinstance(date, datetime) else datetime.fromisoformat(date)

        exchange_listings.sort(key=get_listing_date, reverse=True)

        # Split exchange listings into chunks
        for chunk_index in range(0, len(exchange_listings), self.LISTINGS_PER_MESSAGE):
            chunk = exchange_listings[chunk_index:chunk_index + self.LISTINGS_PER_MESSAGE]
            total_chunks = (len(exchange_listings) - 1) // self.LISTINGS_PER_MESSAGE + 1
            current_part = chunk_index//self.LISTINGS_PER_MESSAGE + 1

            # Create message header
            if total_chunks > 1:
                message = f"🔔 {exchange} New Listings (Part {current_part}/{total_chunks})\n\n"
            else:
                message = f"🔔 {exchange} New Listings\n\n"

            # Add listings to message
            for listing in chunk:
                # Format the listing
                listing_body = await self.format_listing(listing)

                # Create a NotificationMessage for the listing
                listing_notification = NotificationMessage(
                    title="",  # Empty title to avoid adding it to the formatted message
                    body=listing_body,
                    metadata={}  # Empty metadata to avoid adding it to the formatted message
                )

                # Use the format_message function to format the listing
                formatted_listing = await self.format_message(listing_notification)

                # Extract just the body part (skip title, metadata, and timestamp)
                # The format is: title\n---\nbody\n\nMetadata:\n...\n\nTimestamp: ...
                # We want just the body part
                body_start = formatted_listing.find("---\n") + 4  # Skip the "---\n"
                body_end = formatted_listing.find("\n\nMetadata:") if "\n\nMetadata:" in formatted_listing else formatted_listing.find("\n\nTimestamp:")
                listing_message = formatted_listing[body_start:body_end].strip() + "\n\n"

                message += listing_message

            # Send the chunk
            notification = NotificationMessage(
                title=f"{exchange} New Listings (Part {current_part})",
                body=message,
                metadata={
                    "exchange": exchange,
                    "listings": len(chunk), 
                    "part": current_part, 
                    "total_parts": total_chunks
                }
            )

            success = await self.send(notification)
            if not success:
                self.logger.error(f"Failed to send {exchange} listings (Part {current_part})")

            # Add a small delay between messages to avoid rate limiting
            if chunk_index + self.LISTINGS_PER_MESSAGE < len(exchange_listings) or exchange != all_exchanges[-1]:
                await asyncio.sleep(self.MESSAGE_DELAY)

    async def notify_new_listings(self, listings: List[Dict[str, Any]]) -> bool:
        """Send notification about new listings."""
        if not listings:
            return True

        try:
            # Deduplicate listings
            deduplicated_listings = self._deduplicate_listings(listings)

            # Group listings by exchange
            listings_by_exchange = self._group_listings_by_exchange(deduplicated_listings)

            # Get sorted list of exchanges for consistent ordering
            all_exchanges = sorted(listings_by_exchange.keys())

            # Send detailed listings organized by exchange
            for exchange, exchange_listings in listings_by_exchange.items():
                await self._send_exchange_listings(exchange, exchange_listings, all_exchanges)

            return True
        except Exception as exception:
            self.logger.error(f"Error processing notifications: {str(exception)}", exc_info=True)
            return False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the session."""
        if self._session:
            await self._session.close()
            self._session = None
