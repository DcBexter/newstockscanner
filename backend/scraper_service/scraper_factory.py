"""
Factory for creating scraper instances.

This module provides a factory for creating scraper instances based on exchange codes.
It implements the ScraperFactoryInterface to support dependency injection.
"""

from typing import Dict, List, Optional, Type

from backend.core.interfaces import ScraperFactoryInterface
from backend.scraper_service.scrapers.base import BaseScraper
from backend.scraper_service.scrapers.frankfurt_scraper import FrankfurtScraper
from backend.scraper_service.scrapers.hkex_scraper import HKEXScraper
from backend.scraper_service.scrapers.nasdaq_scraper import NasdaqScraper


class ScraperFactory(ScraperFactoryInterface):
    """Factory for creating scraper instances."""

    def __init__(self, scraper_classes: Optional[Dict[str, Type[BaseScraper]]] = None):
        """
        Initialize the scraper factory with scraper classes.

        Args:
            scraper_classes: A dictionary mapping exchange codes to scraper classes.
                            If None, default scraper classes will be used.
        """
        self.scraper_classes = scraper_classes or {
            "hkex": HKEXScraper,
            "nasdaq": NasdaqScraper,
            "nyse": NasdaqScraper,  # Using NasdaqScraper for NYSE as it can extract NYSE listings too
            "fse": FrankfurtScraper,  # Frankfurt Stock Exchange
        }

    def get_scraper(self, exchange_code: str) -> BaseScraper:
        """
        Get a scraper for the specified exchange.

        Args:
            exchange_code: The code of the exchange to get a scraper for.

        Returns:
            A scraper instance for the specified exchange.

        Raises:
            ValueError: If the exchange code is not supported.
        """
        exchange_code = exchange_code.lower()
        if exchange_code not in self.scraper_classes:
            raise ValueError(f"Unsupported exchange code: {exchange_code}")

        return self.scraper_classes[exchange_code]()

    def get_supported_exchanges(self) -> List[str]:
        """
        Get a list of all supported exchange codes.

        Returns:
            A list of exchange codes that are supported by this factory.
        """
        return list(self.scraper_classes.keys())

    def filter_exchanges(self, exchange_filter: Optional[str] = None) -> List[str]:
        """
        Filter exchanges based on the exchange filter.

        This method returns a subset of exchange codes based on the exchange filter,
        or all exchange codes if no filter is provided.

        Args:
            exchange_filter (str, optional): The exchange code to filter by.
                                           If None, all exchange codes will be returned.

        Returns:
            List[str]: A list of exchange codes.
        """
        if not exchange_filter:
            return self.get_supported_exchanges()

        exchange_filter = exchange_filter.lower()
        if exchange_filter in self.scraper_classes:
            return [exchange_filter]

        # If the exchange filter is not supported, return all exchanges
        return self.get_supported_exchanges()
