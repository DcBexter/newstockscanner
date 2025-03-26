# Standardized Logging Format

This document describes the standardized logging format used across all services in the Stock Scanner application.

## Overview

The Stock Scanner application uses a standardized logging format to ensure consistency across all services. The logging format includes:

- Timestamp with ISO 8601 format
- Service name for identifying which service generated the log
- Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Module/service name
- Request ID for tracing requests across services
- Message
- Additional context (when available)

## Log Formats

The application supports two log formats:

### Standard Format

The standard format is designed for human readability while still maintaining a consistent format across all logs:

```
timestamp [service] [request_id] level [module:line] message
```

Example:
```
2023-06-15T12:34:56.789012 [api_service] [550e8400-e29b-41d4-a716-446655440000] INFO [app:42] Application startup complete
```

### JSON Format

The JSON format is designed for machine readability and easier parsing by log analysis tools:

```json
{
  "timestamp": "2023-06-15T12:34:56.789012",
  "service": "api_service",
  "hostname": "server1",
  "level": "INFO",
  "logger": "app",
  "message": "Application startup complete",
  "module": "app",
  "function": "lifespan",
  "line": 42,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Configuration

The logging format can be configured using environment variables:

- `LOG_LEVEL`: The minimum log level to output (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO
- `LOG_FORMAT`: The log format to use (standard, json). Default: standard
- `SERVICE_NAME`: The name of the service for identification in logs. Default: stockscanner

## Request ID Tracing

The application uses request IDs to trace requests across services. Request IDs are:

1. Generated for each incoming request if not provided
2. Passed between services using the `X-Request-ID` header
3. Included in all log messages related to the request

## Usage

### Basic Logging

```python

from backend.config.logging import get_logger

logger = get_logger(__name__)

# Log messages at different levels
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
```

### Logging with Context

```python
# Log with exception information
try:
    # Some code that might raise an exception
    raise ValueError("Something went wrong")
except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
```

### Setting up Logging

```python
from backend.config.logging import setup_logging

# Set up logging with service name
setup_logging(service_name="my_service")
```

## Best Practices

1. **Use the appropriate log level**: Use DEBUG for detailed information, INFO for general information, WARNING for potential issues, ERROR for errors that don't prevent the application from running, and CRITICAL for errors that prevent the application from running.

2. **Include context**: Include relevant context in log messages, such as user IDs, request IDs, and other information that might be useful for debugging.

3. **Be consistent**: Use consistent terminology and formatting in log messages to make them easier to search and analyze.

4. **Log at service boundaries**: Log requests and responses at service boundaries to make it easier to trace requests across services.

5. **Use structured logging**: Use structured logging (JSON format) when possible to make logs easier to parse and analyze.