from datetime import datetime
from typing import List

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


class TimestampMixin:
    """Mixin for adding created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class Exchange(TimestampMixin, Base):
    """Model for stock exchanges."""

    __tablename__ = "exchanges"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    listings: Mapped[List["StockListing"]] = relationship("StockListing", back_populates="exchange", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Exchange(code={self.code}, name={self.name})>"


class StockListing(TimestampMixin, Base):
    """Model for stock listings."""

    __tablename__ = "stock_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    listing_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="New Listing", index=True)
    security_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Equity", index=True)
    remarks: Mapped[str] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(255), nullable=True)
    listing_detail_url: Mapped[str] = mapped_column(String(255), nullable=True)
    notified: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)

    # Foreign keys
    exchange_id: Mapped[int] = mapped_column(ForeignKey("exchanges.id"), nullable=False, index=True)

    # Relationships
    exchange: Mapped[Exchange] = relationship("Exchange", back_populates="listings")

    def __repr__(self) -> str:
        return f"<StockListing(symbol={self.symbol}, name={self.name})>"


class NotificationLog(TimestampMixin, Base):
    """Model for tracking notifications sent."""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error: Mapped[str] = mapped_column(Text, nullable=True)
    notification_metadata: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string

    def __repr__(self) -> str:
        return f"<NotificationLog(type={self.notification_type}, status={self.status})>"
