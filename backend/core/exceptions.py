class StockScannerError(Exception):
    """Base exception for all StockScanner errors."""
    pass

class ScraperError(StockScannerError):
    """Base exception for scraper-related errors."""
    pass

class HTTPError(ScraperError):
    """Exception raised for HTTP-related errors."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")

class ParsingError(ScraperError):
    """Exception raised when parsing data fails."""
    pass

class ValidationError(StockScannerError):
    """Exception raised when data validation fails."""
    pass

class NotifierError(StockScannerError):
    """Exception raised for notification-related errors."""
    pass

class DatabaseError(StockScannerError):
    """Exception raised for database-related errors."""
    pass

class ConfigurationError(StockScannerError):
    """Exception raised for configuration-related errors."""
    pass

class SchedulerError(StockScannerError):
    """Exception raised for scheduler-related errors."""
    pass 
