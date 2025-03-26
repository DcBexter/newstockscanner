import re
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Tuple, Optional


class DateUtils:
    """Utility class for date-related operations.

    This class provides methods for parsing dates in different formats,
    handling errors gracefully, and providing default values when parsing fails.
    """

    # Common date formats
    US_FORMAT = '%m/%d/%Y'       # MM/DD/YYYY (US format)
    ISO_FORMAT = '%Y-%m-%d'       # YYYY-MM-DD (ISO format)
    UK_FORMAT = '%d/%m/%Y'       # DD/MM/YYYY (UK/HK format)
    GERMAN_FORMAT = '%d.%m.%Y'   # DD.MM.YYYY (German format)

    @staticmethod
    def parse_date(date_str: str, default_date: Optional[datetime] = None) -> datetime:
        """Parse a date string in multiple common formats.

        This method tries to parse a date string in multiple formats and returns
        the parsed date if successful, or a default date if parsing fails.

        Args:
            date_str: The date string to parse
            default_date: The default date to return if parsing fails (defaults to None,
                         which will use current date + 30 days)

        Returns:
            A datetime object representing the parsed date, or the default date if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return default_date or (datetime.now() + timedelta(days=30))

        # Try different date formats
        formats = [
            DateUtils.US_FORMAT,      # MM/DD/YYYY
            DateUtils.ISO_FORMAT,     # YYYY-MM-DD
            DateUtils.UK_FORMAT,      # DD/MM/YYYY
            DateUtils.GERMAN_FORMAT   # DD.MM.YYYY
        ]

        for fmt in formats:
            with suppress(ValueError):
                return datetime.strptime(date_str.strip(), fmt)

        # If all formats fail, try regex-based parsing for German format with dots
        with suppress(Exception):
            match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
            if match:
                day, month, year = match.groups()
                return datetime(int(year), int(month), int(day))

        # Return default date if all parsing attempts fail
        return default_date or (datetime.now() + timedelta(days=30))

    @staticmethod
    def parse_date_with_format(date_str: str, date_format: str, 
                              default_date: Optional[datetime] = None) -> datetime:
        """Parse a date string with a specific format.

        Args:
            date_str: The date string to parse
            date_format: The format string (e.g., '%Y-%m-%d')
            default_date: The default date to return if parsing fails

        Returns:
            A datetime object representing the parsed date, or the default date if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return default_date or (datetime.now() + timedelta(days=30))

        try:
            return datetime.strptime(date_str.strip(), date_format)
        except ValueError:
            return default_date or (datetime.now() + timedelta(days=30))

    @staticmethod
    def extract_date_from_text(text: str, default_date: Optional[datetime] = None) -> datetime:
        """Extract and parse a date from text using regex patterns.

        This method looks for common date patterns in text and tries to parse them.

        Args:
            text: The text containing a date
            default_date: The default date to return if extraction fails

        Returns:
            A datetime object representing the extracted date, or the default date if extraction fails
        """
        if not text or not isinstance(text, str):
            return default_date or (datetime.now() + timedelta(days=30))

        # Try to match common date patterns
        patterns = [
            # MM/DD/YYYY
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))),
            # DD/MM/YYYY
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))),
            # YYYY-MM-DD
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
            # DD.MM.YYYY
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', lambda m: datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))))
        ]

        for pattern, parser in patterns:
            match = re.search(pattern, text)
            if match:
                with suppress(Exception):
                    return parser(match)

        # Return default date if all extraction attempts fail
        return default_date or (datetime.now() + timedelta(days=30))


class HKEXUtils:
    """Utility class for HKEX-related functionality."""

    # URL parameters for different search scopes
    BASIC_SEARCH_SCOPE = "Market%20Data|Listing"
    EXPANDED_SEARCH_SCOPE = "Market%20Data|Products|Services|Listing|News|FAQ|Global"

    @staticmethod
    def get_listing_detail_url(symbol: str, name: str, status: str = None) -> Tuple[Optional[str], str]:
        """Get the listing detail URL and security type for a given symbol and name.
        For some securities (especially during corporate actions or new listings),
        no detail page may exist on the exchange website.

        Args:
            symbol: The stock symbol
            name: The stock name
            status: The stock status (optional)

        Returns:
            A tuple of (url, security_type) where url may be None if no detail page exists
        """
        clean_symbol = symbol.lstrip('0')  # Remove leading zeros

        # Define corporate actions that typically don't have detail pages
        no_page_actions = [
            'Share Consolidation',
            'Trading in the Nil Paid Rights',
            'Suspended',
            'Delisted',
            'Stock Split'
        ]

        # First determine the security type
        if 'Note' in name or 'Bond' in name or 'B28' in name:
            security_type = "Bond/Note"
        elif symbol.startswith('85'):
            security_type = "Futures/Options"
        elif 'RTS' in name:
            security_type = "Rights Issue"
        else:
            security_type = "Equity"

        # For corporate actions, use expanded search scope
        if status and any(action in status for action in no_page_actions):
            search_scope = HKEXUtils.EXPANDED_SEARCH_SCOPE
        else:
            # Use simpler URL for regular securities
            search_scope = HKEXUtils.BASIC_SEARCH_SCOPE

        base_url = f"https://www.hkex.com.hk/Global/HKEX-Market-Search-Result?sc_lang=en&q={clean_symbol}&sym={clean_symbol}&u={search_scope}"
        return (base_url, security_type) 
