import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config.logging import setup_logging, get_logger, set_request_id
from backend.config.settings import get_settings
from backend.core.exceptions import DatabaseError
from backend.core.models import NotificationMessage
from backend.database.session import get_db
from backend.notification_service.service import NotificationService

# Set up logging
setup_logging(service_name="notification_service")
logger = get_logger(__name__)

# Get settings
settings = get_settings()

# Import metrics module (requires prometheus_client to be installed)
try:
    from backend.core.metrics import setup_metrics, metrics
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False

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

# Set up metrics collection if enabled
if METRICS_ENABLED:
    logger.info("Setting up metrics collection")
    setup_metrics(app)

    # Add notification-specific metrics
    metrics.counter('notifications_sent_total', 'Total number of notifications sent', ['type'])
    metrics.counter('notifications_failed_total', 'Total number of failed notifications', ['type', 'error_type'])
    metrics.histogram('notification_processing_seconds', 'Time to process notifications in seconds', ['type'])
    metrics.gauge('notification_queue_size', 'Number of notifications in the queue')
else:
    logger.info("Metrics collection is disabled")

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint to verify that the notification service and its dependencies are working.

    This endpoint checks the database connection and returns information about
    the service status. It can be used by monitoring tools to verify that the
    service is operational.

    Args:
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        dict: A dictionary containing the service status and dependency statuses.
    """
    logger.debug("Health check requested")

    # Check database connection
    db_status = "connected"
    try:
        # Simple database query to verify connection
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = f"error: {str(e)}"

    # Check Telegram configuration
    telegram_status = "configured"
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        telegram_status = "not configured"

    # Overall status is healthy only if all dependencies are working
    overall_status = "healthy" if db_status == "connected" else "degraded"

    return {
        "status": overall_status,
        "service": "notification",
        "dependencies": {
            "database": db_status,
            "telegram": telegram_status
        },
        "timestamp": datetime.now().isoformat()
    }

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
    start_time = time.time()
    try:
        logger.info(f"Starting background notification task with notifier: {notifier_type}")

        # Record metrics if enabled
        if METRICS_ENABLED:
            metrics.gauge('notification_queue_size').inc()

        await service.initialize()
        result = await service.send(message, notifier_type)

        logger.info(f"Background notification completed successfully: {result}")

        # Record success metrics if enabled
        if METRICS_ENABLED:
            metrics.counter('notifications_sent_total').labels(notifier_type).inc()

    except Exception as e:
        logger.error(f"Error in background notification: {str(e)}", exc_info=True)

        # Record error metrics if enabled
        if METRICS_ENABLED:
            error_type = type(e).__name__
            metrics.counter('notifications_failed_total').labels(notifier_type, error_type).inc()

    finally:
        # Record processing time if enabled
        if METRICS_ENABLED:
            duration = time.time() - start_time
            metrics.histogram('notification_processing_seconds').labels(notifier_type).observe(duration)
            metrics.gauge('notification_queue_size').dec()

        await service.cleanup()

async def notify_listings_background(service: NotificationService, listings: List[Dict[str, Any]], notifier_type: str):
    """Send notifications about new listings in the background."""
    start_time = time.time()
    try:
        logger.info(f"Starting background listing notification task for {len(listings)} listings with notifier: {notifier_type}")

        # Record metrics if enabled
        if METRICS_ENABLED:
            metrics.gauge('notification_queue_size').inc(len(listings))

        await service.initialize()
        result = await service.notify_new_listings(listings, notifier_type)

        logger.info(f"Background listing notification completed successfully: {len(listings)} listings processed")

        # Record success metrics if enabled
        if METRICS_ENABLED:
            metrics.counter('notifications_sent_total').labels(notifier_type).inc(len(listings))

    except Exception as e:
        logger.error(f"Error in background listing notification: {str(e)}", exc_info=True)

        # Record error metrics if enabled
        if METRICS_ENABLED:
            error_type = type(e).__name__
            metrics.counter('notifications_failed_total').labels(notifier_type, error_type).inc(len(listings))

    finally:
        # Record processing time if enabled
        if METRICS_ENABLED:
            duration = time.time() - start_time
            metrics.histogram('notification_processing_seconds').labels(notifier_type).observe(duration)
            metrics.gauge('notification_queue_size').dec(len(listings))

        await service.cleanup()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True) 
