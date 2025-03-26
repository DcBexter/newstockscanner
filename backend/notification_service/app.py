from typing import List, Dict, Any, Optional
import logging
import uuid

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import DatabaseError
from backend.core.models import NotificationMessage
from backend.database.session import get_db
from backend.notification_service.service import NotificationService
from backend.config.logging import setup_logging, get_logger, set_request_id

# Set up logging
setup_logging(service_name="notification_service")
logger = get_logger(__name__)

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to set a unique request ID for each request."""

    async def dispatch(self, request: Request, call_next):
        # Get request ID from header or generate a new one
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Set the request ID in the context variable
        set_request_id(request_id)

        # Add the request ID to the response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response

app = FastAPI(title="Notification Service API", description="API for sending notifications")

# Add request ID middleware
app.add_middleware(RequestIDMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint."""
    logger.debug("Health check requested")
    return {"status": "healthy", "service": "notification"}

@app.post("/api/v1/notifications/send")
async def send_notification(
    message: NotificationMessage,
    background_tasks: BackgroundTasks,
    notifier_type: str = "telegram",
    db: AsyncSession = Depends(get_db)
):
    """Send a notification."""
    logger.info(f"Received request to send notification with title: {message.title}")
    try:
        # Initialize service
        notification_service = NotificationService(db)

        # Run in background to avoid blocking
        background_tasks.add_task(send_notification_background, notification_service, message, notifier_type)

        logger.info(f"Notification queued for background processing: {message.title}")
        return {"status": "processing", "message": "Notification is being sent in the background"}
    except Exception as e:
        logger.error(f"Failed to queue notification: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")

@app.post("/api/v1/notifications/listings")
async def notify_new_listings(
    listings: List[Dict[str, Any]],
    background_tasks: BackgroundTasks,
    notifier_type: str = "telegram",
    db: AsyncSession = Depends(get_db)
):
    """Send notifications about new listings."""
    logger.info(f"Received request to notify about {len(listings)} listings")
    if not listings:
        logger.warning("No listings provided, skipping notification")
        return {"status": "skipped", "message": "No listings provided"}

    try:
        # Initialize service
        notification_service = NotificationService(db)

        # Run in background to avoid blocking
        background_tasks.add_task(notify_listings_background, notification_service, listings, notifier_type)

        logger.info(f"Listing notifications queued for background processing: {len(listings)} listings")
        return {"status": "processing", "message": f"Processing notifications for {len(listings)} listings"}
    except Exception as e:
        logger.error(f"Failed to queue listing notifications: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process notifications: {str(e)}")

@app.get("/api/v1/notifications/logs")
async def get_notification_logs(
    status: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get notification logs."""
    logger.info(f"Retrieving notification logs with filters: status={status}, days={days}, limit={limit}")
    try:
        notification_service = NotificationService(db)
        logs = await notification_service.get_logs(status=status, days=days, limit=limit)
        logger.info(f"Retrieved {len(logs)} notification logs")
        return {"logs": [{"id": log.id, 
                          "type": log.notification_type, 
                          "title": log.title, 
                          "status": log.status, 
                          "created_at": log.created_at} 
                         for log in logs]}
    except DatabaseError as e:
        logger.error(f"Failed to retrieve notification logs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Background tasks
async def send_notification_background(service: NotificationService, message: NotificationMessage, notifier_type: str):
    """Send a notification in the background."""
    try:
        logger.info(f"Starting background notification task with notifier: {notifier_type}")
        await service.initialize()
        result = await service.send(message, notifier_type)
        logger.info(f"Background notification completed successfully: {result}")
    except Exception as e:
        logger.error(f"Error in background notification: {str(e)}", exc_info=True)
    finally:
        await service.cleanup()

async def notify_listings_background(service: NotificationService, listings: List[Dict[str, Any]], notifier_type: str):
    """Send notifications about new listings in the background."""
    try:
        logger.info(f"Starting background listing notification task for {len(listings)} listings with notifier: {notifier_type}")
        await service.initialize()
        result = await service.notify_new_listings(listings, notifier_type)
        logger.info(f"Background listing notification completed successfully: {len(listings)} listings processed")
    except Exception as e:
        logger.error(f"Error in background listing notification: {str(e)}", exc_info=True)
    finally:
        await service.cleanup()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True) 
