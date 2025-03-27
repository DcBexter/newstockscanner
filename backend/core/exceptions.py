class StockScannerError(Exception):
    """Base exception for all StockScanner errors."""

    pass


# Scraper Exceptions
class ScraperError(StockScannerError):
    """Base exception for scraper-related errors."""

    def __init__(self, message: str = None, status_code: int = None, url: str = None):
        self.status_code = status_code
        self.url = url
        super().__init__(message or "Scraper error occurred")


class CircuitBreakerError(ScraperError):
    """Exception raised when the circuit breaker is open."""

    def __init__(self, message: str = None, url: str = None):
        super().__init__(message or "Circuit breaker is open - target service appears to be down", status_code=503, url=url)


class HTTPError(ScraperError):
    """Exception raised for HTTP-related errors."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}", status_code=status_code)


class TimeoutError(ScraperError):
    """Exception raised when a request times out."""

    def __init__(self, message: str = None, url: str = None, timeout: int = None):
        timeout_msg = f" after {timeout}s" if timeout else ""
        super().__init__(message or f"Request timed out{timeout_msg}", status_code=408, url=url)


class RateLimitError(HTTPError):
    """Exception raised when rate limiting is encountered."""

    def __init__(self, message: str = None, retry_after: int = None, url: str = None):
        retry_msg = f", retry after {retry_after}s" if retry_after else ""
        super().__init__(status_code=429, message=f"{message or 'Rate limit exceeded'}{retry_msg}")
        self.url = url
        self.retry_after = retry_after


class ConnectionError(ScraperError):
    """Exception raised when connection to the server fails."""

    def __init__(self, message: str = None, url: str = None):
        super().__init__(message or "Failed to connect to server", status_code=503, url=url)


class ServerError(HTTPError):
    """Exception raised for server-side errors (5xx)."""

    def __init__(self, status_code: int, message: str = None, url: str = None):
        if not (500 <= status_code < 600):
            status_code = 500
        super().__init__(status_code=status_code, message=message or f"Server error: {status_code}")
        self.url = url


class ClientError(HTTPError):
    """Exception raised for client-side errors (4xx)."""

    def __init__(self, status_code: int, message: str = None, url: str = None):
        if not (400 <= status_code < 500):
            status_code = 400
        super().__init__(status_code=status_code, message=message or f"Client error: {status_code}")
        self.url = url


# Parsing Exceptions
class ParsingError(ScraperError):
    """Exception raised when parsing data fails."""

    pass


class DataNotFoundError(ParsingError):
    """Exception raised when required data is not found in the content."""

    def __init__(self, message: str = None, element: str = None):
        element_msg = f" '{element}'" if element else ""
        super().__init__(message or f"Required data{element_msg} not found in content")


class DataFormatError(ParsingError):
    """Exception raised when data is in an unexpected format."""

    def __init__(self, message: str = None, expected_format: str = None, actual_data: str = None):
        format_msg = f", expected format: {expected_format}" if expected_format else ""
        super().__init__(message or f"Data format error{format_msg}")
        self.expected_format = expected_format
        self.actual_data = actual_data


class DateParsingError(DataFormatError):
    """Exception raised when parsing dates fails."""

    def __init__(self, message: str = None, date_string: str = None, expected_format: str = None):
        date_msg = f" '{date_string}'" if date_string else ""
        format_msg = f" (expected format: {expected_format})" if expected_format else ""
        super().__init__(message or f"Failed to parse date{date_msg}{format_msg}")
        self.date_string = date_string
        self.expected_format = expected_format


class JSONParsingError(DataFormatError):
    """Exception raised when parsing JSON data fails."""

    def __init__(self, message: str = None, json_error: str = None):
        error_msg = f": {json_error}" if json_error else ""
        super().__init__(message or f"Failed to parse JSON data{error_msg}")
        self.json_error = json_error


# Validation Exceptions
class ValidationError(StockScannerError):
    """Exception raised when data validation fails."""

    pass


class SchemaError(ValidationError):
    """Exception raised when data doesn't match the expected schema."""

    def __init__(self, message: str = None, field: str = None, details: dict = None):
        field_msg = f" for field '{field}'" if field else ""
        super().__init__(message or f"Schema validation error{field_msg}")
        self.field = field
        self.details = details


class RequiredFieldError(ValidationError):
    """Exception raised when a required field is missing."""

    def __init__(self, message: str = None, field: str = None):
        super().__init__(message or f"Required field{' ' + field if field else ''} is missing")
        self.field = field


class DataTypeError(ValidationError):
    """Exception raised when a field has the wrong data type."""

    def __init__(self, message: str = None, field: str = None, expected_type: str = None, actual_type: str = None):
        field_msg = f" '{field}'" if field else ""
        type_msg = f", expected {expected_type}, got {actual_type}" if expected_type and actual_type else ""
        super().__init__(message or f"Invalid data type for field{field_msg}{type_msg}")
        self.field = field
        self.expected_type = expected_type
        self.actual_type = actual_type


# Notifier Exceptions
class NotifierError(StockScannerError):
    """Exception raised for notification-related errors."""

    pass


class NotifierAuthenticationError(NotifierError):
    """Exception raised for authentication errors with notification services."""

    def __init__(self, message: str = None, service: str = None):
        service_msg = f" for {service}" if service else ""
        super().__init__(message or f"Authentication failed{service_msg}")
        self.service = service


class NotifierCommunicationError(NotifierError):
    """Exception raised when sending notifications fails."""

    def __init__(self, message: str = None, service: str = None, status_code: int = None):
        service_msg = f" to {service}" if service else ""
        status_msg = f" (status code: {status_code})" if status_code else ""
        super().__init__(message or f"Failed to send notification{service_msg}{status_msg}")
        self.service = service
        self.status_code = status_code


class NotifierFormattingError(NotifierError):
    """Exception raised when formatting notification messages fails."""

    def __init__(self, message: str = None, template: str = None):
        template_msg = f" for template '{template}'" if template else ""
        super().__init__(message or f"Failed to format message{template_msg}")
        self.template = template


class NotifierInitializationError(NotifierError):
    """Exception raised when initializing notification services fails."""

    def __init__(self, message: str = None, service: str = None):
        service_msg = f" {service}" if service else ""
        super().__init__(message or f"Failed to initialize notifier{service_msg}")
        self.service = service


class NotifierNotFoundError(NotifierError):
    """Exception raised when a requested notifier is not found."""

    def __init__(self, message: str = None, notifier_type: str = None):
        type_msg = f" '{notifier_type}'" if notifier_type else ""
        super().__init__(message or f"Notifier{type_msg} not found")
        self.notifier_type = notifier_type


# Database Exceptions
class DatabaseError(StockScannerError):
    """Exception raised for database-related errors."""

    pass


class DatabaseQueryError(DatabaseError):
    """Exception raised when retrieving data from the database fails."""

    def __init__(self, message: str = None, query: str = None, params: dict = None):
        super().__init__(message or "Failed to execute database query")
        self.query = query
        self.params = params


class DatabaseUpdateError(DatabaseError):
    """Exception raised when updating data in the database fails."""

    def __init__(self, message: str = None, model: str = None, record_id: str = None):
        model_msg = f" {model}" if model else ""
        id_msg = f" with ID {record_id}" if record_id else ""
        super().__init__(message or f"Failed to update{model_msg}{id_msg}")
        self.model = model
        self.record_id = record_id


class DatabaseCreateError(DatabaseError):
    """Exception raised when creating data in the database fails."""

    def __init__(self, message: str = None, model: str = None):
        model_msg = f" {model}" if model else ""
        super().__init__(message or f"Failed to create{model_msg}")
        self.model = model


class DatabaseDeleteError(DatabaseError):
    """Exception raised when deleting data from the database fails."""

    def __init__(self, message: str = None, model: str = None, record_id: str = None):
        model_msg = f" {model}" if model else ""
        id_msg = f" with ID {record_id}" if record_id else ""
        super().__init__(message or f"Failed to delete{model_msg}{id_msg}")
        self.model = model
        self.record_id = record_id


class DatabaseNotFoundError(DatabaseError):
    """Exception raised when a requested resource is not found in the database."""

    def __init__(self, message: str = None, model: str = None, record_id: str = None):
        model_msg = f" {model}" if model else ""
        id_msg = f" with ID {record_id}" if record_id else ""
        super().__init__(message or f"Record not found{model_msg}{id_msg}")
        self.model = model
        self.record_id = record_id


class DatabaseTransactionError(DatabaseError):
    """Exception raised for database transaction-related errors."""

    def __init__(self, message: str = None, operation: str = None):
        operation_msg = f" during {operation}" if operation else ""
        super().__init__(message or f"Transaction failed{operation_msg}")
        self.operation = operation


class ConfigurationError(StockScannerError):
    """Exception raised for configuration-related errors."""

    pass


class SchedulerError(StockScannerError):
    """Exception raised for scheduler-related errors."""

    pass
