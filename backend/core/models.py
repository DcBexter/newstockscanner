from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ListingBase(BaseModel):
    """Base model for stock listings."""

    name: str
    symbol: str
    listing_date: datetime
    lot_size: int
    status: str = Field(default="New Listing")
    exchange_code: str
    url: Optional[str] = None
    security_type: str = Field(default="Equity")
    listing_detail_url: Optional[str] = None


class ListingCreate(ListingBase):
    """Model for creating a new listing."""

    pass


class Listing(ListingBase):
    """Model for a listing with database fields."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedListings(BaseModel):
    """Model for paginated listings response."""

    items: List[Listing]
    total: int
    skip: int
    limit: int


class ExchangeBase(BaseModel):
    """Base model for exchanges."""

    name: str
    code: str
    url: str
    description: Optional[str] = None


class ExchangeCreate(ExchangeBase):
    """Model for creating a new exchange."""

    pass


class Exchange(ExchangeBase):
    """Model for an exchange with database fields."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationMessage(BaseModel):
    """Model for notification messages."""

    title: str
    body: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)


class ScrapingResult(BaseModel):
    """Model for scraping results."""

    success: bool
    message: str
    data: List[ListingBase] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
