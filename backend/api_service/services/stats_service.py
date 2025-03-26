from typing import Dict, Any, Optional
from datetime import datetime, timedelta, UTC
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import StockListing, Exchange
from backend.core.exceptions import DatabaseError, DatabaseQueryError

class StatsService:
    """Service for managing statistics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_listing_stats(
        self,
        days: int = 30,
        exchange_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get listing statistics for the specified period."""
        try:
            since = datetime.now(UTC) - timedelta(days=days)

            # Get all the stats components
            summary_stats = await self._get_summary_stats(since, exchange_code)
            daily_counts = await self._get_daily_counts(since, exchange_code)
            exchange_stats = await self._get_exchange_stats(since, exchange_code)

            # Format response to match frontend expectations
            return {
                "total": summary_stats["total"],
                "total_all_time": summary_stats["total_all_time"],
                "statuses": summary_stats["statuses"],
                "security_types": summary_stats["security_types"],
                "daily_stats": daily_counts,  # Renamed from daily_counts to daily_stats
                "exchange_stats": exchange_stats  # This is now a direct array matching frontend expectations
            }
        except Exception as e:
            raise DatabaseQueryError(f"Failed to get statistics: {str(e)}") from e

    async def _get_summary_stats(
        self,
        since: datetime,
        exchange_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for the specified period."""
        try:
            # Build the base query
            query = select(func.count(StockListing.id)).join(Exchange)

            # Add filters
            query_filtered = query.where(StockListing.listing_date >= since.replace(tzinfo=None))
            if exchange_code:
                query_filtered = query_filtered.where(Exchange.code == exchange_code)

            # Execute queries
            result = await self.db.execute(query_filtered)
            total_filtered = result.scalar() or 0

            # Get total all-time if we have a filtered period
            result = await self.db.execute(query)
            total_all_time = result.scalar() or 0

            # Get different status counts
            statuses = {}
            status_query = select(
                StockListing.status,
                func.count(StockListing.id)
            ).join(Exchange).where(
                StockListing.listing_date >= since.replace(tzinfo=None)
            )

            if exchange_code:
                status_query = status_query.where(Exchange.code == exchange_code)

            status_query = status_query.group_by(StockListing.status)
            result = await self.db.execute(status_query)

            for status, count in result:
                statuses[status] = count

            # Get security types counts
            security_types = {}
            type_query = select(
                StockListing.security_type,
                func.count(StockListing.id)
            ).join(Exchange).where(
                StockListing.listing_date >= since.replace(tzinfo=None)
            )

            if exchange_code:
                type_query = type_query.where(Exchange.code == exchange_code)

            type_query = type_query.group_by(StockListing.security_type)
            result = await self.db.execute(type_query)

            for security_type, count in result:
                security_types[security_type] = count

            return {
                "total": total_filtered,
                "total_all_time": total_all_time,
                "statuses": statuses,
                "security_types": security_types
            }
        except Exception as e:
            raise DatabaseQueryError(f"Failed to get summary statistics: {str(e)}") from e

    async def _get_exchange_stats(
        self,
        since: datetime,
        exchange_code: Optional[str] = None
    ) -> list:
        """Get statistics by exchange."""
        try:
            # Query for exchange breakdown
            query = select(
                Exchange.code,
                Exchange.name,
                func.count(StockListing.id).label("count")
            ).join(
                StockListing
            ).where(
                StockListing.listing_date >= since.replace(tzinfo=None)
            )

            if exchange_code:
                query = query.where(Exchange.code == exchange_code)

            query = query.group_by(Exchange.code, Exchange.name)
            query = query.order_by(func.count(StockListing.id).desc())

            result = await self.db.execute(query)

            # Return as a simple array that exactly matches frontend expectations
            exchange_stats = []
            for code, name, count in result:
                exchange_stats.append({
                    "code": code,
                    "name": name,
                    "total_listings": count  # Changed from "count" to "total_listings" to match frontend
                })

            return exchange_stats
        except Exception as e:
            raise DatabaseQueryError(f"Failed to get exchange statistics: {str(e)}") from e

    async def _get_daily_counts(
        self,
        since: datetime,
        exchange_code: Optional[str] = None
    ) -> list:
        """Get daily counts for the specified period."""
        try:
            # Use simpler date extraction for PostgreSQL
            date_extract = func.date_trunc('day', StockListing.listing_date)

            # Build the query to get counts by date
            query = select(
                date_extract.label("date"),
                func.count(StockListing.id).label("count")
            ).join(Exchange).where(
                StockListing.listing_date >= since.replace(tzinfo=None)
            )

            if exchange_code:
                query = query.where(Exchange.code == exchange_code)

            query = query.group_by(date_extract)
            query = query.order_by(date_extract)

            result = await self.db.execute(query)

            # Format the results
            daily_counts = []
            for date, count in result:
                daily_counts.append({
                    "date": date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date),
                    "count": count
                })

            # Fill in missing dates with zero counts
            filled_counts = []
            current_date = since.replace(tzinfo=None)
            end_date = datetime.now(UTC).replace(tzinfo=None)

            # Create a lookup dictionary for easy access
            date_dict = {item["date"]: item["count"] for item in daily_counts}

            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                filled_counts.append({
                    "date": date_str,
                    "count": date_dict.get(date_str, 0)
                })
                current_date += timedelta(days=1)

            return filled_counts
        except Exception as e:
            raise DatabaseQueryError(f"Failed to get daily counts: {str(e)}") from e
