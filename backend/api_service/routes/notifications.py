"""
Routes for notification operations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import NotificationMessage
from backend.database.session import get_db
from backend.notification_service.service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)

@router.post("/send")
async def send_notification(
    message: NotificationMessage,
    notifier_type: str = "telegram",
    db: AsyncSession = Depends(get_db)
):
    """Send a notification."""
    service = NotificationService(db)
    try:
        await service.initialize()
        return await service.send(message, notifier_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/logs")
async def get_notification_logs(
    status: str = None,
    days: int = 7,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get notification logs with optional filters."""
    service = NotificationService(db)
    try:
        return await service.get_logs(status, days, limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 
