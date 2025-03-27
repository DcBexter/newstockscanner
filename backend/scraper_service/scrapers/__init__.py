"""Scrapers for the Stock Scanner application"""

from backend.scraper_service.scrapers.base import BaseScraper
from backend.scraper_service.scrapers.frankfurt_scraper import FrankfurtScraper
from backend.scraper_service.scrapers.hkex_scraper import HKEXScraper
from backend.scraper_service.scrapers.nasdaq_scraper import NasdaqScraper

__all__ = ["BaseScraper", "HKEXScraper", "NasdaqScraper", "FrankfurtScraper"]
