"""
FastAPI application for the Stock Scanner API service.

This module defines the FastAPI application for the Stock Scanner API service,
which provides REST API endpoints for accessing stock listings, exchanges,
statistics, and other functionality. It includes middleware configuration,
exception handlers, and health check endpoints.

The application uses SQLAlchemy for database access and includes proper
startup and shutdown handlers for resource management.
"""

from contextlib import asynccontextmanager
import uuid
from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from backend.database.session import get_db, init_db, close_db
from backend.config.settings import get_settings
from backend.config.log_config import setup_logging, set_request_id
from backend.core.exceptions import StockScannerError
from backend.api_service.routes import router

# Import metrics module (requires prometheus_client to be installed)
try:
    from backend.core.metrics import setup_metrics, metrics
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    logging.warning("Prometheus client not installed. Metrics collection is disabled.")
    logging.warning("To enable metrics, install prometheus-client: pip install prometheus-client")

    # Define dummy metrics and setup_metrics when prometheus_client is not available
    def setup_metrics(app):
        """Dummy setup_metrics function when prometheus_client is not available."""
        pass

    class DummyMetrics:
        """Dummy metrics class when prometheus_client is not available."""
        def counter(self, name, description='', labels=None):
            return self

        def histogram(self, name, description='', labels=None, buckets=None):
            return self

        def gauge(self, name, description='', labels=None):
            return self

        def labels(self, *args, **kwargs):
            return self

        def inc(self, value=1):
            pass

        def dec(self, value=1):
            pass

        def observe(self, value):
            pass

    metrics = DummyMetrics()

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

settings = get_settings()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.

    This replaces the deprecated on_event handlers with a context manager
    that handles startup and shutdown events. It initializes resources like
    logging and database connections on startup and cleans them up on shutdown.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Control is yielded back to the application during its lifetime.
    """
    # Startup: Initialize application
    setup_logging(service_name="api_service")
    logger.info("Initializing application...")

    # Initialize database
    logger.info("Initializing database...")
    await init_db()

    logger.info("Application startup complete")

    yield  # Application runs here

    # Shutdown: Clean up resources
    logger.info("Shutting down application...")

    # Close database connections
    logger.info("Closing database connections...")
    await close_db()

    logger.info("Application shutdown complete")

# Create the app instance
app = FastAPI(
    title="Stock Scanner API",
    description="API for the Stock Scanner application",
    version="0.1.0",
    lifespan=lifespan,
)

# Add request ID middleware
app.add_middleware(RequestIDMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up metrics collection if enabled
if METRICS_ENABLED:
    logger.info("Setting up metrics collection")
    setup_metrics(app)

    # Add API-specific metrics
    metrics.counter('api_listings_requests_total', 'Total number of requests to the listings endpoint')
    metrics.counter('api_exchanges_requests_total', 'Total number of requests to the exchanges endpoint')
    metrics.counter('api_stats_requests_total', 'Total number of requests to the stats endpoint')
    metrics.gauge('api_active_db_connections', 'Number of active database connections')
else:
    logger.info("Metrics collection is disabled")

@app.get("/")
async def root():
    """
    Root endpoint to check if the API is running.

    This endpoint provides a simple way to verify that the API service
    is up and running.

    Returns:
        dict: A message indicating that the API is running.
    """
    return {"message": "Stock Scanner API is running"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint to verify that the API and database are working.

    This endpoint performs a simple database query to verify that the
    connection to the database is working properly. It returns information
    about the API version and database connection status.

    Args:
        db (AsyncSession): The database session, injected by FastAPI.

    Returns:
        dict: A dictionary containing the API status, version, and database status.
    """
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
    """
    Handle StockScanner-specific exceptions.

    This exception handler catches StockScannerError exceptions and returns
    a JSON response with the error message and type. It also logs the error
    for debugging purposes.

    Args:
        request (Request): The request that caused the exception.
        exc (StockScannerError): The exception that was raised.

    Returns:
        JSONResponse: A JSON response containing the error message and type.
    """
    logger.error(f"StockScanner error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "type": exc.__class__.__name__}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions.

    This exception handler catches all unexpected exceptions and returns
    a generic error message to avoid exposing sensitive information.
    It logs the full error details for debugging purposes.

    Args:
        request (Request): The request that caused the exception.
        exc (Exception): The exception that was raised.

    Returns:
        JSONResponse: A JSON response with a generic error message.
    """
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

# Include API routes
app.include_router(router, prefix="/api/v1")

# If this file is run directly (not imported), run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
