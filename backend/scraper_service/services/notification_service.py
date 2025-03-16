"""Notification service for the scraper service."""

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Dict, Any

import aiohttp

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications about new stock listings."""
    
    def __init__(self, notification_url=None):
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 5  # seconds
        self.notification_service_url = notification_url or os.getenv("NOTIFICATION_SERVICE_URL", "http://notification_service:8001")
    
    async def send_listing_notifications(self, listings: List[Dict[str, Any]]) -> bool:
        """Send notifications by calling the notification service API."""
        if not listings:
            logger.info("No new listings to notify about")
            return True
            
        # Convert datetime objects to string to make them JSON serializable
        serializable_listings = []
        for listing in listings:
            serialized_listing = {}
            for key, value in listing.items():
                if isinstance(value, datetime):
                    serialized_listing[key] = value.isoformat()
                else:
                    serialized_listing[key] = value
            serializable_listings.append(serialized_listing)
            
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"Sending notifications via API for {len(serializable_listings)} new listings")
                
                # Create the API endpoint URL
                api_url = f"{self.notification_service_url}/api/v1/notifications/listings"
                
                # Send the request to the notification service
                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, json=serializable_listings) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"Notification service response: {result}")
                            return True
                        else:
                            error_text = await response.text()
                            logger.warning(f"Failed to send notifications: HTTP {response.status} - {error_text}")
                            
                            if attempt < self.MAX_RETRIES - 1:
                                logger.warning(f"Retrying in {self.RETRY_DELAY} seconds... (Attempt {attempt + 1}/{self.MAX_RETRIES})")
                                await asyncio.sleep(self.RETRY_DELAY)
                                continue
                            
                            logger.error("Max retries exceeded for notification request")
                            return False
                
            except Exception as e:
                error_msg = f"Error sending notifications via API: {str(e)}"
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"{error_msg}. Retrying in {self.RETRY_DELAY} seconds... (Attempt {attempt + 1}/{self.MAX_RETRIES})")
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    logger.error(f"{error_msg}. Max retries exceeded.")
        
        return False 