import asyncio
from enum import IntEnum
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, TypeVar

import aiohttp
from aiohttp import ClientTimeout

if TYPE_CHECKING:
    pass

from backend.core.exceptions import ConfigurationError, NotifierError
from backend.core.models import NotificationMessage
from backend.notification_service.notifiers.base import BaseNotifier

# Type variable for the return type of the function being decorated
T = TypeVar("T")


class HttpStatus(IntEnum):
    """HTTP status codes used in the application."""

    OK = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404


def with_retry(
    max_retries: int = 3, retry_delay: int = 5, logger=None, error_class: type = NotifierError
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        logger: Logger instance for logging retry attempts
        error_class: Exception class to raise on failure

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Get logger from first argument (self) if not provided
            nonlocal logger
            if logger is None and args and hasattr(args[0], "logger"):
                logger = args[0].logger

            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except aiohttp.ClientError as client_error:
                    last_exception = client_error
                    error_msg = f"Network error during {func.__name__}: {str(client_error)}"

                    if attempt < max_retries - 1:
                        if logger:
                            logger.warning(f"{error_msg}. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                    else:
                        if logger:
                            logger.error(f"{error_msg}. Max retries exceeded.")
                        raise error_class(error_msg) from client_error
                except Exception as exception:
                    if logger:
                        logger.error(f"Unexpected error during {func.__name__}: {str(exception)}")
                    raise error_class(f"Unexpected error during {func.__name__}: {str(exception)}") from exception

            # This should never be reached due to the raise in the loop,
            # but added for completeness
            if last_exception:
                raise error_class(f"Failed after {max_retries} retries") from last_exception
            return None  # To satisfy type checker

        return wrapper

    return decorator


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

    def _mask_token(self, token: str) -> str:
        """
        Mask a token for secure logging.

        Args:
            token: The token to mask

        Returns:
            A masked version of the token
        """
        return f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "token_too_short"

    async def _process_bot_verification_response(self, response: aiohttp.ClientResponse) -> None:
        """
        Process the response from the bot verification request.

        Args:
            response: The HTTP response from the Telegram API

        Raises:
            NotifierError: If the bot verification fails
        """
        text = await response.text()
        self.logger.debug(f"Received response: {text}")

        if not response.ok:
            error_msg = f"HTTP {response.status}: {text}"

            if response.status == HttpStatus.NOT_FOUND:
                self.logger.error(f"Bot not found. Please verify your TELEGRAM_BOT_TOKEN is correct: {error_msg}")
                raise NotifierError(f"Bot not found. Invalid token: {error_msg}")
            elif response.status == HttpStatus.UNAUTHORIZED:
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

    @with_retry(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
    async def _make_bot_verification_request(self) -> None:
        """
        Make a request to the Telegram API to verify the bot.

        Raises:
            NotifierError: If the bot verification fails
        """
        token = self.settings.TELEGRAM_BOT_TOKEN
        masked_token = self._mask_token(token)
        url = f"{self.base_url}{token}/getMe"

        self.logger.info(f"Making request to Telegram API URL: {self.base_url}{masked_token}/getMe")
        self.logger.debug(f"Full unmasked URL for debugging: {url}")

        async with self.session.get(url) as response:
            await self._process_bot_verification_response(response)

    async def _verify_bot(self) -> None:
        """Verify bot token and permissions."""
        self.logger.info("Verifying Telegram bot...")
        token = self.settings.TELEGRAM_BOT_TOKEN
        masked_token = self._mask_token(token)
        self.logger.info(f"Using Telegram bot token: {masked_token}")

        await self._make_bot_verification_request()

    async def _process_send_message_response(self, response: aiohttp.ClientResponse, message: NotificationMessage) -> bool:
        """
        Process the response from sending a message to Telegram.

        Args:
            response: The HTTP response from the Telegram API
            message: The notification message that was sent

        Returns:
            bool: True if the message was sent successfully, False otherwise

        Raises:
            NotifierError: If there was an error sending the message
        """
        text = await response.text()

        if not response.ok:
            error_msg = f"HTTP {response.status}: {text}"

            if response.status == HttpStatus.FORBIDDEN:
                self.logger.error(f"Bot was blocked by the user or chat. Please check TELEGRAM_CHAT_ID: {error_msg}")
                raise NotifierError(f"Bot was blocked or chat not found: {error_msg}")
            elif response.status == HttpStatus.BAD_REQUEST:
                self.logger.error(f"Bad request. Please check message format: {error_msg}")
                raise NotifierError(f"Bad request: {error_msg}")
            else:
                self.logger.error(f"Failed to send message: {error_msg}")
                raise NotifierError(f"Failed to send message: {error_msg}")

        result = await response.json()
        success = result.get("ok", False)

        # Log the result
        self.logger.info(f"Notification sent: success={success}, " f"type={self.__class__.__name__}, " f"title={message.title}")

        if not success:
            self.logger.error(f"Notification error: {str(result)}")
        else:
            self.logger.info("Message sent successfully")

        return success

    def _create_message_payload(self, formatted_message: str) -> dict:
        """
        Create the payload for sending a message to Telegram.

        Args:
            formatted_message: The formatted message text

        Returns:
            dict: The payload for the Telegram API
        """
        return {"chat_id": self.settings.TELEGRAM_CHAT_ID, "text": formatted_message, "parse_mode": "HTML", "disable_web_page_preview": True}

    @with_retry(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
    async def _send_message_to_telegram(self, message: NotificationMessage, formatted_message: str) -> bool:
        """
        Send a message to Telegram.

        Args:
            message: The notification message to send
            formatted_message: The formatted message text

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        url = f"{self.base_url}{self.settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = self._create_message_payload(formatted_message)

        self.logger.debug("Sending message to Telegram")
        async with self.session.post(url, json=data) as response:
            return await self._process_send_message_response(response, message)

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
        try:
            formatted_message = await self.format_message(message)
            return await self._send_message_to_telegram(message, formatted_message)
        except Exception as exception:
            # Log the error and return False instead of re-raising
            error_msg = f"Error sending message: {str(exception)}"
            self.logger.error(error_msg)
            self.logger.info(f"Notification sent: success=False, " f"type={self.__class__.__name__}, " f"title={message.title}")
            return False
