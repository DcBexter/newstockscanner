import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.cache import cache
from backend.core.exceptions import DatabaseQueryError
from backend.database.models import StockListing, Exchange

logger = logging.getLogger(__name__)

# Constants
CACHE_EXPIRATION_SECONDS = 300  # 5 minutes


class StatsService:
    """Service for managing statistics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_listing_stats(
        self,
        days: int = 30,
        exchange_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get listing statistics for the specified period.

        This method retrieves statistics about stock listings for the specified period.
        Results are cached for 5 minutes to improve performance.

        Args:
            days (int, optional): Number of days to include in the statistics. Defaults to 30.
            exchange_code (Optional[str], optional): Filter by exchange code. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing the statistics.

        Raises:
            DatabaseQueryError: If there's an error retrieving statistics from the database.
        """
        try:
            # Try to get cached result first
            cache_key = self._generate_cache_key(days, exchange_code)
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                logger.debug(f"Using cached statistics for days={days}, exchange={exchange_code or 'all'}")
                return cached_result

            # If not in cache, compute the result
            since = self._calculate_since_date(days)

            # Get all the stats components
            summary_stats = await self._get_summary_stats(since, exchange_code)
            daily_counts = await self._get_daily_counts(since, exchange_code)
            exchange_stats = await self._get_exchange_stats(since, exchange_code)

            # Format and cache the result
            result = self._format_result(summary_stats, daily_counts, exchange_stats)
            self._cache_result(cache_key, result)

            logger.info(f"Generated fresh statistics for days={days}, exchange={exchange_code or 'all'}")
            return result
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}", exc_info=True)
            raise DatabaseQueryError(f"Failed to get statistics: {str(e)}") from e

    @staticmethod
    def _generate_cache_key(days: int, exchange_code: Optional[str]) -> str:
        """Generate a cache key based on the parameters."""
        return f"stats:listing_stats:{days}:{exchange_code or 'all'}"

    @staticmethod
    def _get_cached_result(cache_key: str) -> Optional[Dict[str, Any]]:
        """Get the result from the cache if available."""
        return cache.get(cache_key)

    @staticmethod
    def _cache_result(cache_key: str, result: Dict[str, Any]) -> None:
        """Cache the result for future use."""
        cache.set(cache_key, result, expire=CACHE_EXPIRATION_SECONDS)

    @staticmethod
    def _calculate_since_date(days: int) -> datetime:
        """Calculate the start date for the statistics period."""
        return datetime.now(UTC) - timedelta(days=days)

    @staticmethod
    def _format_result(
            summary_stats: Dict[str, Any],
        daily_counts: List[Dict[str, Any]], 
        exchange_stats: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format the statistics result to match frontend expectations."""
        return {
            "total": summary_stats["total"],
            "total_all_time": summary_stats["total_all_time"],
            "statuses": summary_stats["statuses"],
            "security_types": summary_stats["security_types"],
            "daily_stats": daily_counts,
            "exchange_stats": exchange_stats
        }

    @staticmethod
    def _build_base_query():
        """Build the base query for listing counts."""
        return select(func.count(StockListing.id)).join(Exchange)

    @staticmethod
    def _apply_filters(query, since: datetime, exchange_code: Optional[str] = None):
        """Apply common filters to a query."""
        # Add date filter
        filtered_query = query.where(StockListing.listing_date >= since.replace(tzinfo=None))

        # Add exchange filter if provided
        if exchange_code:
            filtered_query = filtered_query.where(Exchange.code == exchange_code)

        return filtered_query

    async def _get_total_count(self, query) -> int:
        """Execute a count query and return the result."""
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def _get_grouped_counts(
        self, 
        group_field, 
        since: datetime, 
        exchange_code: Optional[str] = None
    ) -> Dict[str, int]:
        """Get counts grouped by a specific field."""
        # Build the query
        query = select(
            group_field,
            func.count(StockListing.id)
        ).join(Exchange)

        # Apply filters
        query = self._apply_filters(query, since, exchange_code)

        # Group by the field
        query = query.group_by(group_field)

        # Execute the query
        result = await self.db.execute(query)

        # Convert to dictionary
        counts = {}
        for field_value, count in result:
            counts[field_value] = count

        return counts

    async def _get_summary_stats(
        self,
        since: datetime,
        exchange_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for the specified period."""
        try:
            # Get total counts
            base_query = self._build_base_query()
            filtered_query = self._apply_filters(base_query, since, exchange_code)

            total_filtered = await self._get_total_count(filtered_query)
            total_all_time = await self._get_total_count(base_query)

            # Get counts by status
            statuses = await self._get_grouped_counts(
                StockListing.status, 
                since, 
                exchange_code
            )

            # Get counts by security type
            security_types = await self._get_grouped_counts(
                StockListing.security_type, 
                since, 
                exchange_code
            )

            return {
                "total": total_filtered,
                "total_all_time": total_all_time,
                "statuses": statuses,
                "security_types": security_types
            }
        except Exception as e:
            logger.error(f"Failed to get summary statistics: {str(e)}", exc_info=True)
            raise DatabaseQueryError(f"Failed to get summary statistics: {str(e)}") from e

    async def _build_exchange_stats_query(
        self,
        since: datetime,
        exchange_code: Optional[str] = None
    ):
        """Build a query for exchange statistics."""
        # Query for exchange breakdown
        query = select(
            Exchange.code,
            Exchange.name,
            func.count(StockListing.id).label("count")
        ).join(StockListing)

        # Apply filters
        query = self._apply_filters(query, since, exchange_code)

        # Group and order
        query = query.group_by(Exchange.code, Exchange.name)
        query = query.order_by(func.count(StockListing.id).desc())

        return query

    @staticmethod
    def _format_exchange_stats(result) -> List[Dict[str, Any]]:
        """Format exchange statistics to match frontend expectations."""
        exchange_stats = []
        for code, name, count in result:
            exchange_stats.append({
                "code": code,
                "name": name,
                "total_listings": count  # Using "total_listings" to match frontend expectations
            })
        return exchange_stats

    async def _get_exchange_stats(
        self,
        since: datetime,
        exchange_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get statistics by exchange."""
        try:
            # Build and execute query
            query = await self._build_exchange_stats_query(since, exchange_code)
            result = await self.db.execute(query)

            # Format the results
            return self._format_exchange_stats(result)
        except Exception as e:
            logger.error(f"Failed to get exchange statistics: {str(e)}", exc_info=True)
            raise DatabaseQueryError(f"Failed to get exchange statistics: {str(e)}") from e

    async def _build_daily_counts_query(
        self,
        since: datetime,
        exchange_code: Optional[str] = None
    ):
        """Build a query for daily counts."""
        # Use date extraction for PostgreSQL
        date_extract = func.date_trunc('day', StockListing.listing_date)

        # Build the query to get counts by date
        query = select(
            date_extract.label("date"),
            func.count(StockListing.id).label("count")
        ).join(Exchange)

        # Apply filters
        query = self._apply_filters(query, since, exchange_code)

        # Group and order
        query = query.group_by(date_extract)
        query = query.order_by(date_extract)

        return query

    @staticmethod
    def _format_date(date) -> str:
        """Format a date object to a string in YYYY-MM-DD format."""
        return date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)

    def _format_daily_counts(self, result) -> List[Dict[str, Any]]:
        """Format daily counts to match frontend expectations."""
        daily_counts = []
        for date, count in result:
            daily_counts.append({
                "date": self._format_date(date),
                "count": count
            })
        return daily_counts

    def _fill_missing_dates(
        self, 
        daily_counts: List[Dict[str, Any]], 
        since: datetime
    ) -> List[Dict[str, Any]]:
        """Fill in missing dates with zero counts."""
        # Create a lookup dictionary for easy access
        date_dict = {item["date"]: item["count"] for item in daily_counts}

        # Fill in missing dates
        filled_counts = []
        current_date = since.replace(tzinfo=None)
        end_date = datetime.now(UTC).replace(tzinfo=None)

        while current_date <= end_date:
            date_str = self._format_date(current_date)
            filled_counts.append({
                "date": date_str,
                "count": date_dict.get(date_str, 0)
            })
            current_date += timedelta(days=1)

        return filled_counts

    async def _get_daily_counts(
        self,
        since: datetime,
        exchange_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get daily counts for the specified period."""
        try:
            # Build and execute query
            query = await self._build_daily_counts_query(since, exchange_code)
            result = await self.db.execute(query)

            # Format the results
            daily_counts = self._format_daily_counts(result)

            # Fill in missing dates
            return self._fill_missing_dates(daily_counts, since)
        except Exception as e:
            logger.error(f"Failed to get daily counts: {str(e)}", exc_info=True)
            raise DatabaseQueryError(f"Failed to get daily counts: {str(e)}") from e
