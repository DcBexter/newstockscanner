import logging
import logging.handlers
import sys
import json
import socket
import uuid
import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import os
from logging.handlers import RotatingFileHandler
from contextvars import ContextVar

from backend.config.settings import get_settings

settings = get_settings()

# Context variable to store request ID
request_id_var: ContextVar[str] = ContextVar('request_id', default='')

def get_request_id() -> str:
    """Get the current request ID or generate a new one if not set."""
    request_id = request_id_var.get()
    if not request_id:
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
    return request_id

def set_request_id(request_id: str) -> None:
    """Set the request ID for the current context."""
    request_id_var.set(request_id)

class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the log record.

    This formatter is designed to make logs easier to parse and analyze
    by outputting them in a structured JSON format.
    """
    def __init__(self, service_name: str = None):
        super().__init__()
        self.service_name = service_name or os.getenv("SERVICE_NAME", "stockscanner")
        self.hostname = socket.gethostname()

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "service": self.service_name,
            "hostname": self.hostname,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request ID if available
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id

        # Add exception info if available
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        # Add extra fields from the record
        if hasattr(record, 'extra'):
            log_data.update(record.extra)

        return json.dumps(log_data)

class StandardFormatter(logging.Formatter):
    """
    Formatter that outputs logs in a standardized format.

    This formatter is designed for human readability while still
    maintaining a consistent format across all logs.
    """
    def __init__(self, service_name: str = None):
        super().__init__()
        self.service_name = service_name or os.getenv("SERVICE_NAME", "stockscanner")

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record in a standardized format."""
        timestamp = datetime.datetime.fromtimestamp(record.created).isoformat()
        request_id = get_request_id()
        request_id_str = f"[{request_id}]" if request_id else ""

        # Format: timestamp [service] [request_id] level [module:line] message
        log_line = f"{timestamp} [{self.service_name}] {request_id_str} {record.levelname} [{record.name}:{record.lineno}] {record.getMessage()}"

        # Add exception info if available
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"

        return log_line

def setup_logging(log_file: Optional[Path] = None, service_name: str = None) -> None:
    """
    Configure logging for the application.

    This function sets up logging with standardized formatters for both
    console and file output. It configures the root logger and sets
    appropriate log levels for third-party libraries.

    Args:
        log_file (Optional[Path]): Path to the log file. If None, only console logging is enabled.
        service_name (str): Name of the service for identification in logs.
    """
    # Get log level from environment variable
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Determine if we should use JSON logging
    use_json = os.getenv("LOG_FORMAT", "standard").lower() == "json"

    # Get service name from environment or parameter
    service_name = service_name or os.getenv("SERVICE_NAME", "stockscanner")

    # Create formatters
    if use_json:
        console_formatter = JsonFormatter(service_name)
        file_formatter = JsonFormatter(service_name)
    else:
        console_formatter = StandardFormatter(service_name)
        file_formatter = StandardFormatter(service_name)

    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)

    handlers = [console_handler]

    if log_file:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = handlers

    # Set levels for third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aioschedule").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name (str): Name of the logger, typically __name__.

    Returns:
        logging.Logger: A logger instance with the specified name.
    """
    return logging.getLogger(name)
