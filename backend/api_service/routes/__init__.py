"""
API routes package for the Stock Scanner application.

This package contains the API routes for the Stock Scanner application,
organized into separate modules by functionality:
- listings: Routes for stock listing operations
- exchanges: Routes for exchange operations
- stats: Routes for statistics operations
- notifications: Routes for notification operations
- scrape: Routes for scraping operations

The main router is created here and all sub-routers are included.
"""

from fastapi import APIRouter

from backend.api_service.routes import exchanges, listings, notifications, scrape, stats
from backend.config.settings import get_settings

settings = get_settings()

# Create main router without prefix (prefix is added in app.py)
router = APIRouter()

# Include all sub-routers
router.include_router(listings.router)
router.include_router(exchanges.router)
router.include_router(stats.router)
router.include_router(notifications.router)
router.include_router(scrape.router)

__all__ = ["router"]
