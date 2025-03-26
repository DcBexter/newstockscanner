from typing import Optional, List, Dict, Any
import aiohttp
from urllib.parse import urljoin
from datetime import datetime
import asyncio
from aiohttp import ClientTimeout
import html

from backend.notification_service.notifiers.base import BaseNotifier
from backend.core.models import NotificationMessage
from backend.core.exceptions import NotifierError, ConfigurationError

class TelegramNotifier(BaseNotifier):
    """Telegram notifier implementation."""

    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    REQUEST_TIMEOUT = 30  # seconds

    def __init__(self):
        super().__init__()
        self.base_url = "https://api.telegram.org/bot"
        self._session: Optional[aiohttp.ClientSession] = None

        # Validate configuration
        if not self.settings.TELEGRAM_BOT_TOKEN:
            self.logger.error("TELEGRAM_BOT_TOKEN is not configured")
            raise ConfigurationError("TELEGRAM_BOT_TOKEN is not configured")
        if not self.settings.TELEGRAM_CHAT_ID:
            self.logger.error("TELEGRAM_CHAT_ID is not configured")
            raise ConfigurationError("TELEGRAM_CHAT_ID is not configured")

        self.logger.info("Telegram notifier initialized with bot token and chat ID")

    @property
    def session(self) -> aiohttp.ClientSession:
        if not self._session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")
        return self._session

    async def initialize(self) -> None:
        """Initialize the Telegram notifier."""
        self.logger.info("Initializing Telegram notifier...")
        timeout = ClientTimeout(total=self.REQUEST_TIMEOUT)
        self._session = aiohttp.ClientSession(timeout=timeout)
        await self._verify_bot()

    async def _verify_bot(self) -> None:
        """Verify bot token and permissions."""
        self.logger.info("Verifying Telegram bot...")
        token = self.settings.TELEGRAM_BOT_TOKEN
        masked_token = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "token_too_short"
        self.logger.info(f"Using Telegram bot token: {masked_token}")

        for attempt in range(self.MAX_RETRIES):
            try:
                url = f"{self.base_url}{token}/getMe"
                self.logger.info(f"Making request to Telegram API URL: {self.base_url}{masked_token}/getMe")
                self.logger.debug(f"Full unmasked URL for debugging: {url}")
                self.logger.debug(f"Sending verification request to Telegram API (attempt {attempt + 1}/{self.MAX_RETRIES})")

                async with self.session.get(url) as response:
                    text = await response.text()
                    self.logger.debug(f"Received response: {text}")
                    if not response.ok:
                        error_msg = f"HTTP {response.status}: {text}"
                        if response.status == 404:
                            self.logger.error(f"Bot not found. Please verify your TELEGRAM_BOT_TOKEN is correct: {error_msg}")
                            raise NotifierError(f"Bot not found. Invalid token: {error_msg}")
                        elif response.status == 401:
                            self.logger.error(f"Unauthorized. Please verify your TELEGRAM_BOT_TOKEN is valid: {error_msg}")
                            raise NotifierError(f"Unauthorized. Invalid token: {error_msg}")
                        else:
                            self.logger.error(f"Failed to verify bot: {error_msg}")
                            raise NotifierError(f"Failed to verify bot: {error_msg}")

                    data = await response.json()
                    if not data.get("ok"):
                        error_msg = f"Bot verification failed: {data.get('description', 'Unknown error')}"
                        self.logger.error(error_msg)
                        raise NotifierError(error_msg)

                    self.logger.info(f"Bot verified successfully: @{data['result']['username']}")
                    return

            except aiohttp.ClientError as e:
                error_msg = f"Network error during bot verification: {str(e)}"
                if attempt < self.MAX_RETRIES - 1:
                    self.logger.warning(f"{error_msg}. Retrying in {self.RETRY_DELAY} seconds...")
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    self.logger.error(f"{error_msg}. Max retries exceeded.")
                    raise NotifierError(error_msg) from e
            except Exception as e:
                error_msg = f"Unexpected error during bot verification: {str(e)}"
                self.logger.error(error_msg)
                raise NotifierError(error_msg) from e

    async def send(self, message: NotificationMessage) -> bool:
        """Send a message via Telegram."""
        for attempt in range(self.MAX_RETRIES):
            try:
                formatted_message = await self.format_message(message)
                url = f"{self.base_url}{self.settings.TELEGRAM_BOT_TOKEN}/sendMessage"

                data = {
                    "chat_id": self.settings.TELEGRAM_CHAT_ID,
                    "text": formatted_message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True
                }

                self.logger.debug(f"Sending message to Telegram (attempt {attempt + 1}/{self.MAX_RETRIES})")
                async with self.session.post(url, json=data) as response:
                    text = await response.text()
                    if not response.ok:
                        error_msg = f"HTTP {response.status}: {text}"
                        if response.status == 403:
                            self.logger.error(f"Bot was blocked by the user or chat. Please check TELEGRAM_CHAT_ID: {error_msg}")
                            raise NotifierError(f"Bot was blocked or chat not found: {error_msg}")
                        elif response.status == 400:
                            self.logger.error(f"Bad request. Please check message format: {error_msg}")
                            raise NotifierError(f"Bad request: {error_msg}")
                        else:
                            if attempt < self.MAX_RETRIES - 1:
                                self.logger.warning(f"Failed to send message: {error_msg}. Retrying in {self.RETRY_DELAY} seconds...")
                                await asyncio.sleep(self.RETRY_DELAY)
                                continue
                            self.logger.error(f"Failed to send message: {error_msg}. Max retries exceeded.")
                            raise NotifierError(f"Failed to send message: {error_msg}")

                    result = await response.json()
                    success = result.get("ok", False)

                    await self.log_notification(
                        message,
                        success,
                        None if success else str(result)
                    )

                    if success:
                        self.logger.info("Message sent successfully")
                    return success

            except aiohttp.ClientError as e:
                error_msg = f"Network error while sending message: {str(e)}"
                if attempt < self.MAX_RETRIES - 1:
                    self.logger.warning(f"{error_msg}. Retrying in {self.RETRY_DELAY} seconds...")
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    self.logger.error(f"{error_msg}. Max retries exceeded.")
                    await self.log_notification(message, False, error_msg)
                    return False
            except Exception as e:
                error_msg = f"Unexpected error while sending message: {str(e)}"
                self.logger.error(error_msg)
                await self.log_notification(message, False, error_msg)
                return False

    def _escape_html(self, text: str) -> str:
        """Escape special characters for HTML formatting."""
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    async def notify_new_listings(self, listings: List[Dict[str, Any]]) -> bool:
        """Send notification about new listings."""
        if not listings:
            return True

        # Constants for Telegram limits
        MAX_MESSAGE_LENGTH = 4000  # Slightly less than Telegram's 4096 limit for safety
        LISTINGS_PER_MESSAGE = 10  # Number of listings per message

        try:
            # Step 1: Deduplicate listings based on symbol, exchange_code, and ID (if available)
            unique_listings = {}
            for listing in listings:
                # Include ID in deduplication key if available
                if 'id' in listing:
                    key = f"{listing['exchange_code']}_{listing['symbol']}_{listing['id']}"
                else:
                    key = f"{listing['exchange_code']}_{listing['symbol']}"
                unique_listings[key] = listing

            deduplicated_listings = list(unique_listings.values())
            self.logger.info(f"Deduplicated {len(listings)} listings to {len(deduplicated_listings)} unique entries")

            # Step 2: Group listings by exchange
            listings_by_exchange = {}
            for listing in deduplicated_listings:
                exchange_code = listing['exchange_code']
                if exchange_code not in listings_by_exchange:
                    listings_by_exchange[exchange_code] = []
                listings_by_exchange[exchange_code].append(listing)

            # Step 3: Create a summary message first
            all_exchanges = sorted(listings_by_exchange.keys())
            exchanges_str = ', '.join(all_exchanges)
            total_listings = len(deduplicated_listings)

            summary_message = (
                f"🔔 New Stock Listings Alert\n\n"
                f"Found {total_listings} new listings across {len(all_exchanges)} exchanges:\n"
            )

            for exchange in all_exchanges:
                count = len(listings_by_exchange[exchange])
                summary_message += f"• {exchange}: {count} listings\n"

            summary_message += "\nDetailed listings will follow in separate messages."

            # Send the summary message
            summary_notification = NotificationMessage(
                title=f"New Stock Listings Summary",
                body=summary_message,
                metadata={"type": "summary", "total": total_listings}
            )

            await self.send(summary_notification)
            await asyncio.sleep(1)  # Small delay between messages

            # Step 4: Send detailed listings by exchange
            for exchange, exchange_listings in listings_by_exchange.items():
                # Sort listings by listing date (newest first)
                exchange_listings.sort(
                    key=lambda x: x['listing_date'] if isinstance(x['listing_date'], datetime) 
                    else datetime.fromisoformat(x['listing_date']),
                    reverse=True
                )

                # Split exchange listings into chunks
                for i in range(0, len(exchange_listings), LISTINGS_PER_MESSAGE):
                    chunk = exchange_listings[i:i + LISTINGS_PER_MESSAGE]
                    total_chunks = (len(exchange_listings) - 1) // LISTINGS_PER_MESSAGE + 1

                    # Create message header
                    if total_chunks > 1:
                        message = f"🔔 {exchange} New Listings (Part {i//LISTINGS_PER_MESSAGE + 1}/{total_chunks})\n\n"
                    else:
                        message = f"🔔 {exchange} New Listings\n\n"

                    # Add listings to message
                    for listing in chunk:
                        listing_date = listing['listing_date']
                        if isinstance(listing_date, str):
                            listing_date = datetime.fromisoformat(listing_date)

                        # Escape special characters in text fields
                        name = self._escape_html(listing['name'])
                        symbol = listing['symbol']
                        status = listing['status']
                        security_type = listing['security_type']

                        # Format stock info with URL if available
                        if 'url' in listing and listing['url']:
                            primary_url = listing['url']  # This is the info PDF URL if available
                        else:
                            primary_url = None

                        # Format stock info with info PDF link if available
                        stock_info = f"<a href='{primary_url}'>{symbol}</a>" if primary_url else symbol

                        message += (
                            f"<b>{name}</b> ({stock_info})\n"
                            f"📅 Listing Date: {listing_date.strftime('%Y-%m-%d')}\n"
                            f"📊 Lot Size: {listing['lot_size']:,}\n"
                            f"📝 Status: {status}\n"
                            f"🔖 Type: {security_type}\n"
                        )

                        # Only add detail link if URL exists and is not None
                        if listing.get('listing_detail_url') and listing['listing_detail_url'] is not None:
                            message += f"🌐 <a href='{listing['listing_detail_url']}'>View Details</a>\n"

                        message += "\n"

                    # Send the chunk
                    notification = NotificationMessage(
                        title=f"{exchange} New Listings (Part {i//LISTINGS_PER_MESSAGE + 1})",
                        body=message,
                        metadata={
                            "exchange": exchange,
                            "listings": len(chunk), 
                            "part": i//LISTINGS_PER_MESSAGE + 1, 
                            "total_parts": total_chunks
                        }
                    )

                    success = await self.send(notification)
                    if not success:
                        self.logger.error(f"Failed to send {exchange} listings (Part {i//LISTINGS_PER_MESSAGE + 1})")

                    # Add a small delay between messages to avoid rate limiting
                    if i + LISTINGS_PER_MESSAGE < len(exchange_listings) or exchange != all_exchanges[-1]:
                        await asyncio.sleep(1)

            return True
        except Exception as e:
            self.logger.error(f"Error processing notifications: {str(e)}", exc_info=True)
            return False

    async def format_message(self, message: NotificationMessage) -> str:
        """Format a notification message for Telegram."""
        # Don't escape HTML in the message body since we're using HTML formatting
        return message.body if message.body else ""

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the session."""
        if self._session:
            await self._session.close()
            self._session = None 
