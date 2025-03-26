from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import DatabaseError
from backend.core.models import NotificationMessage
from backend.database.session import get_db
from backend.notification_service.service import NotificationService

app = FastAPI(title="Notification Service API", description="API for sending notifications")

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
    return {"status": "healthy", "service": "notification"}

@app.post("/api/v1/notifications/send")
async def send_notification(
    message: NotificationMessage,
    background_tasks: BackgroundTasks,
    notifier_type: str = "telegram",
    db: AsyncSession = Depends(get_db)
):
    """Send a notification."""
    try:
        # Initialize service
        notification_service = NotificationService(db)
        
        # Run in background to avoid blocking
        background_tasks.add_task(send_notification_background, notification_service, message, notifier_type)
        
        return {"status": "processing", "message": "Notification is being sent in the background"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")

@app.post("/api/v1/notifications/listings")
async def notify_new_listings(
    listings: List[Dict[str, Any]],
    background_tasks: BackgroundTasks,
    notifier_type: str = "telegram",
    db: AsyncSession = Depends(get_db)
):
    """Send notifications about new listings."""
    if not listings:
        return {"status": "skipped", "message": "No listings provided"}
        
    try:
        # Initialize service
        notification_service = NotificationService(db)
        
        # Run in background to avoid blocking
        background_tasks.add_task(notify_listings_background, notification_service, listings, notifier_type)
        
        return {"status": "processing", "message": f"Processing notifications for {len(listings)} listings"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process notifications: {str(e)}")

@app.get("/api/v1/notifications/logs")
async def get_notification_logs(
    status: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get notification logs."""
    try:
        notification_service = NotificationService(db)
        logs = await notification_service.get_logs(status=status, days=days, limit=limit)
        return {"logs": [{"id": log.id, 
                          "type": log.notification_type, 
                          "title": log.title, 
                          "status": log.status, 
                          "created_at": log.created_at} 
                         for log in logs]}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))

# Background tasks
async def send_notification_background(service: NotificationService, message: NotificationMessage, notifier_type: str):
    """Send a notification in the background."""
    try:
        await service.initialize()
        await service.send(message, notifier_type)
    except Exception as e:
        print(f"Error in background notification: {str(e)}")
    finally:
        await service.cleanup()

async def notify_listings_background(service: NotificationService, listings: List[Dict[str, Any]], notifier_type: str):
    """Send notifications about new listings in the background."""
    try:
        await service.initialize()
        await service.notify_new_listings(listings, notifier_type)
    except Exception as e:
        print(f"Error in background listing notification: {str(e)}")
    finally:
        await service.cleanup()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True) 