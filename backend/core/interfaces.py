"""
Interfaces for dependency injection.

This module defines interfaces (abstract base classes) for various services
to support dependency injection and reduce tight coupling between components.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TypeVar, Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import NotificationMessage, ListingBase

T = TypeVar('T')

class DatabaseHelperInterface(ABC):
    """Interface for database helper operations."""

    @abstractmethod
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
        pass

class DatabaseServiceInterface(ABC):
    """Interface for database operations related to stock listings."""

    @abstractmethod
    async def save_listings(self, listings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save listings to the database.

        Args:
            listings: A list of listing data dictionaries to save.

        Returns:
            A dictionary with the results of the operation, including:
            - saved_count: The number of listings successfully saved
            - total: The total number of listings processed
            - new_listings: A list of newly created listings
        """
        pass

class NotificationServiceInterface(ABC):
    """Interface for notification operations."""

    @abstractmethod
    async def send_listing_notifications(self, listings: List[Dict[str, Any]]) -> bool:
        """
        Send notifications for new stock listings.

        Args:
            listings: A list of dictionaries containing the listings to send notifications for.

        Returns:
            bool: True if notifications were sent successfully, False otherwise.
        """
        pass

class ScraperFactoryInterface(ABC):
    """Interface for scraper factory."""

    @abstractmethod
    def get_scraper(self, exchange_code: str):
        """
        Get a scraper for the specified exchange.

        Args:
            exchange_code: The code of the exchange to get a scraper for.

        Returns:
            A scraper instance for the specified exchange.
        """
        pass