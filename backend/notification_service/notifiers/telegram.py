import asyncio
from typing import Optional, TYPE_CHECKING

import aiohttp
from aiohttp import ClientTimeout

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import NotifierError, ConfigurationError
from backend.core.models import NotificationMessage
from backend.notification_service.notifiers.base import BaseNotifier


class TelegramNotifier(BaseNotifier):
    """
    Telegram notifier implementation.
    
    This class is responsible for sending messages to Telegram.
    All formatting and message splitting is handled by the base class.
    """
    # Constants for Telegram-specific settings
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    REQUEST_TIMEOUT = 30  # seconds

    def __init__(self):
        super().__init__()
        self.base_url = "https://api.telegram.org/bot"

        # Validate configuration
        if not self.settings.TELEGRAM_BOT_TOKEN:
            self.logger.error("TELEGRAM_BOT_TOKEN is not configured")
            raise ConfigurationError("TELEGRAM_BOT_TOKEN is not configured")
        if not self.settings.TELEGRAM_CHAT_ID:
            self.logger.error("TELEGRAM_CHAT_ID is not configured")
            raise ConfigurationError("TELEGRAM_CHAT_ID is not configured")

        self.logger.info("Telegram notifier initialized with bot token and chat ID")

    async def initialize(self) -> None:
        """Initialize the Telegram notifier."""
        self.logger.info("Initializing Telegram notifier...")
        # Call parent's initialize to create the session with proper timeout
        await super().initialize()
        # Override the default timeout with our specific timeout
        if self._session:
            self._session._timeout = ClientTimeout(total=self.REQUEST_TIMEOUT)
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

            except aiohttp.ClientError as client_error:
                error_msg = f"Network error during bot verification: {str(client_error)}"
                if attempt < self.MAX_RETRIES - 1:
                    self.logger.warning(f"{error_msg}. Retrying in {self.RETRY_DELAY} seconds...")
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    self.logger.error(f"{error_msg}. Max retries exceeded.")
                    raise NotifierError(error_msg) from client_error
            except Exception as exception:
                error_msg = f"Unexpected error during bot verification: {str(exception)}"
                self.logger.error(error_msg)
                raise NotifierError(error_msg) from exception

    async def send_single_message(self, message: NotificationMessage) -> bool:
        """
        Send a single notification message to Telegram.
        
        This method implements the abstract method from BaseNotifier.
        It handles the actual sending of a message to Telegram.
        
        Args:
            message: The notification message to send.
            
        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        formatted_message = await self.format_message(message)
        
        for attempt in range(self.MAX_RETRIES):
            try:
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

                    # Log to the logger only
                    self.logger.info(
                        f"Notification sent: success={success}, "
                        f"type={self.__class__.__name__}, "
                        f"title={message.title}"
                    )
                    if not success:
                        self.logger.error(f"Notification error: {str(result)}")

                    if success:
                        self.logger.info("Message sent successfully")
                    return success

            except aiohttp.ClientError as client_error:
                error_msg = f"Network error while sending message: {str(client_error)}"
                if attempt < self.MAX_RETRIES - 1:
                    self.logger.warning(f"{error_msg}. Retrying in {self.RETRY_DELAY} seconds...")
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    self.logger.error(f"{error_msg}. Max retries exceeded.")
                    # Log to the logger only
                    self.logger.info(
                        f"Notification sent: success=False, "
                        f"type={self.__class__.__name__}, "
                        f"title={message.title}"
                    )
                    self.logger.error(f"Notification error: {error_msg}")
                    return False
            except Exception as exception:
                error_msg = f"Unexpected error while sending message: {str(exception)}"
                self.logger.error(error_msg)
                # Log to the logger only
                self.logger.info(
                    f"Notification sent: success=False, "
                    f"type={self.__class__.__name__}, "
                    f"title={message.title}"
                )
                self.logger.error(f"Notification error: {error_msg}")
                return False