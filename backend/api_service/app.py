"""
FastAPI application for the API service.
"""

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from backend.database.session import get_db, init_db, close_db
from backend.config.settings import get_settings
from backend.config.logging import setup_logging
from backend.core.exceptions import StockScannerError
from backend.api_service.routes import router

settings = get_settings()
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Stock Scanner API",
        description="API for the Stock Scanner application",
        version="0.1.0",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        """Root endpoint to check if the API is running."""
        return {"message": "Stock Scanner API is running"}

    @app.get("/health")
    async def health_check(db: AsyncSession = Depends(get_db)):
        """Health check endpoint to verify that the API and database are working."""
        try:
            # Simple database query to verify connection
            await db.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        return {
            "status": "ok",
            "api_version": "0.1.0",
            "database": db_status
        }

    # Exception handlers
    @app.exception_handler(StockScannerError)
    async def stockscanner_exception_handler(request: Request, exc: StockScannerError):
        """Handle StockScanner-specific exceptions."""
        logger.error(f"StockScanner error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=400,
            content={"error": str(exc), "type": exc.__class__.__name__}
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

    # Startup and shutdown events
    @app.on_event("startup")
    async def startup():
        """Initialize application on startup."""
        # Setup logging
        setup_logging()
        logger.info("Initializing application...")
        
        # Initialize database
        logger.info("Initializing database...")
        await init_db()
        
        logger.info("Application startup complete")

    @app.on_event("shutdown")
    async def shutdown():
        """Clean up resources on shutdown."""
        logger.info("Shutting down application...")
        
        # Close database connections
        logger.info("Closing database connections...")
        await close_db()
        
        logger.info("Application shutdown complete")

    # Include API routes
    app.include_router(router, prefix="/api/v1")

    return app

# Create the app instance
app = create_app()

# If this file is run directly (not imported), run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
