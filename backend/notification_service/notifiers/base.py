from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime
import json

from backend.core.models import NotificationMessage
from backend.core.exceptions import NotifierError
from backend.config.logging import get_logger
from backend.config.settings import get_settings

settings = get_settings()
logger = get_logger(__name__)

class BaseNotifier(ABC):
    """Base class for all notifiers."""

    def __init__(self):
        self.settings = settings
        self.logger = logger

    @abstractmethod
    async def send(self, message: NotificationMessage) -> bool:
        """Send a notification message."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the notifier with necessary setup."""
        pass

    async def format_message(self, message: NotificationMessage) -> str:
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
        except Exception as e:
            raise NotifierError(f"Failed to format message: {str(e)}") from e

    async def log_notification(
        self,
        message: NotificationMessage,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """Log the notification attempt."""
        try:
            metadata = json.dumps(message.metadata) if message.metadata else None
            
            # Here you would typically save to the database using the NotificationLog model
            self.logger.info(
                f"Notification sent: success={success}, "
                f"type={self.__class__.__name__}, "
                f"title={message.title}"
            )
            if error:
                self.logger.error(f"Notification error: {error}")
        except Exception as e:
            self.logger.error(f"Failed to log notification: {str(e)}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass  # Implement cleanup if needed 
