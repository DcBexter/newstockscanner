from typing import Optional
from pydantic_settings import SettingsConfigDict, BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Debug mode
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost:5432/stockscanner"
    )

    # Scraping
    SCRAPING_INTERVAL_MINUTES: int = int(os.getenv("SCRAPING_INTERVAL_MINUTES", "60"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    USER_AGENT: str = "StockScanner/1.0"

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "30"))
    RATE_LIMIT_DOMAIN_SPECIFIC: bool = os.getenv("RATE_LIMIT_DOMAIN_SPECIFIC", "true").lower() == "true"

    # Incremental scraping
    INCREMENTAL_SCRAPING_ENABLED: bool = os.getenv("INCREMENTAL_SCRAPING_ENABLED", "true").lower() == "true"
    INCREMENTAL_SCRAPING_MAX_DAYS: int = int(os.getenv("INCREMENTAL_SCRAPING_MAX_DAYS", "30"))

    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")

    # Service URLs
    SCRAPER_SERVICE_URL: Optional[str] = os.getenv("SCRAPER_SERVICE_URL", "http://scraper_service:8002")
    NOTIFICATION_SERVICE_URL: Optional[str] = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification_service:8001")

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list = ["*"]  # Default to allow all origins

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

# Example usage:
# from backend.config.settings import get_settings
# settings = get_settings() 
