"""API routes package"""

from fastapi import APIRouter
from backend.config.settings import get_settings

from backend.api_service.routes import listings, exchanges, stats, notifications, scrape

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
