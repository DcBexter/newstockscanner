from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, UTC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import NotificationMessage
from backend.database.models import NotificationLog
from backend.notification_service.notifiers.base import BaseNotifier
from backend.notification_service.notifiers.telegram import TelegramNotifier
from backend.core.exceptions import NotifierError, DatabaseError

class NotificationService:
    """Service for managing notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._notifiers: Dict[str, BaseNotifier] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize notification service."""
        if not self._initialized:
            await self._initialize_notifiers()

    async def send(
        self,
        message: NotificationMessage,
        notifier_type: str = "telegram"
    ) -> bool:
        """Send a notification using the specified notifier."""
        try:
            if not self._initialized:
                await self._initialize_notifiers()

            notifier = self._get_notifier(notifier_type)
            log = await self._create_log(message, notifier_type)

            success = await notifier.send(message)
            await self._update_log(log, success)

            return success
        except Exception as e:
            await self._handle_error(message, notifier_type, str(e))
            raise NotifierError(f"Failed to send notification: {str(e)}")

    async def notify_new_listings(
        self, 
        listings: List[Dict[str, Any]], 
        notifier_type: str = "telegram"
    ) -> bool:
        """Send notifications about new listings."""
        try:
            if not self._initialized:
                await self._initialize_notifiers()

            notifier = self._get_notifier(notifier_type)

            # Check if the notifier has a specialized method for listings
            if hasattr(notifier, 'notify_new_listings'):
                return await notifier.notify_new_listings(listings)

            # Fallback to generic notification
            message = NotificationMessage(
                title="New Stock Listings",
                body=f"Found {len(listings)} new stock listings.",
                metadata={"listings_count": len(listings)}
            )
            return await self.send(message, notifier_type)

        except Exception as e:
            raise NotifierError(f"Failed to send new listings notification: {str(e)}")

    async def get_logs(
        self,
        status: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 100
    ) -> List[NotificationLog]:
        """Get notification logs with optional filters."""
        try:
            query = select(NotificationLog)

            if status:
                query = query.where(NotificationLog.status == status)
            if days:
                # Convert UTC datetime to naive datetime for database comparison
                since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
                query = query.where(NotificationLog.created_at >= since)

            query = query.order_by(NotificationLog.created_at.desc()).limit(limit)

            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Failed to get notification logs: {str(e)}")

    async def _initialize_notifiers(self) -> None:
        """Initialize notification service and register notifiers."""
        try:
            # Initialize Telegram notifier - don't use async with here since we manage the lifecycle
            telegram = TelegramNotifier()
            await telegram.initialize()
            self._notifiers["telegram"] = telegram

            # Add more notifiers here as needed

            self._initialized = True
        except Exception as e:
            raise NotifierError(f"Failed to initialize notification service: {str(e)}")

    def _get_notifier(self, notifier_type: str) -> BaseNotifier:
        """Get a notifier by type."""
        notifier = self._notifiers.get(notifier_type)
        if not notifier:
            raise NotifierError(f"Notifier {notifier_type} not found")
        return notifier

    async def _create_log(
        self,
        message: NotificationMessage,
        notifier_type: str
    ) -> NotificationLog:
        """Create a notification log entry."""
        log = NotificationLog(
            notification_type=notifier_type,
            title=message.title,
            body=message.body,
            status="pending",
            notification_metadata=str(message.metadata) if message.metadata else None
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def _update_log(self, log: NotificationLog, success: bool) -> None:
        """Update a notification log entry with the result."""
        log.status = "sent" if success else "failed"
        if not success:
            log.error = "Failed to send notification"
        await self.db.commit()

    async def _handle_error(
        self,
        message: NotificationMessage,
        notifier_type: str,
        error: str
    ) -> None:
        """Handle and log a notification error."""
        try:
            await self.db.rollback()
            log = NotificationLog(
                notification_type=notifier_type,
                title=message.title,
                body=message.body,
                status="error",
                error=error,
                notification_metadata=str(message.metadata) if message.metadata else None
            )
            self.db.add(log)
            await self.db.commit()
        except Exception as e:
            # Just log the error if we can't save to database
            print(f"Failed to log notification error: {str(e)}")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        for notifier in self._notifiers.values():
            if hasattr(notifier, '__aexit__'):
                await notifier.__aexit__(None, None, None)
        self._initialized = False 
