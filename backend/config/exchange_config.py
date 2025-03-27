"""Configuration for stock exchanges."""

from typing import Any, Dict

# Exchange codes
EXCHANGE_CODES = {"NASDAQ": "NASDAQ", "NYSE": "NYSE", "HKEX": "HKEX", "FSE": "FSE"}

# Exchange data for creation
EXCHANGE_DATA: Dict[str, Dict[str, Any]] = {
    EXCHANGE_CODES["NASDAQ"]: {"name": "NASDAQ Stock Exchange", "code": EXCHANGE_CODES["NASDAQ"], "url": "https://www.nasdaq.com/"},
    EXCHANGE_CODES["NYSE"]: {"name": "New York Stock Exchange", "code": EXCHANGE_CODES["NYSE"], "url": "https://www.nyse.com/"},
    EXCHANGE_CODES["HKEX"]: {"name": "Hong Kong Stock Exchange", "code": EXCHANGE_CODES["HKEX"], "url": "https://www.hkex.com.hk/"},
    EXCHANGE_CODES["FSE"]: {
        "name": "Frankfurt Stock Exchange",
        "code": EXCHANGE_CODES["FSE"],
        "url": "https://www.boerse-frankfurt.de/en",
        "description": "Frankfurt Stock Exchange (Börse Frankfurt)",
    },
}


def get_exchange_data(exchange_code: str) -> Dict[str, Any]:
    """Get exchange data by code."""
    return EXCHANGE_DATA.get(exchange_code)
