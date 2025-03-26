"""
Cache implementation for the Stock Scanner application.

This module provides a simple in-memory cache that can be easily replaced
with a distributed cache like Redis in the future. It supports setting values
with an optional expiration time, getting values, invalidating values, and
checking if values exist.
"""

import time
from datetime import timedelta
from typing import Dict, Optional, Tuple, Union, TypeVar, Generic

T = TypeVar('T')

class Cache(Generic[T]):
    """
    A simple in-memory cache implementation.
    
    This class provides a simple in-memory cache that can be easily replaced
    with a distributed cache like Redis in the future. It supports setting values
    with an optional expiration time, getting values, invalidating values, and
    checking if values exist.
    
    Attributes:
        _cache (Dict[str, Tuple[T, Optional[float]]]): The cache storage.
    """
    
    def __init__(self):
        """Initialize an empty cache."""
        self._cache: Dict[str, Tuple[T, Optional[float]]] = {}
    
    def set(self, key: str, value: T, expire: Optional[Union[int, float, timedelta]] = None) -> None:
        """
        Set a value in the cache.
        
        Args:
            key (str): The key to store the value under.
            value (T): The value to store.
            expire (Optional[Union[int, float, timedelta]], optional): The expiration time.
                If an int or float, it's interpreted as seconds from now.
                If a timedelta, it's interpreted as a duration from now.
                If None, the value never expires. Defaults to None.
        """
        if expire is None:
            expiration = None
        elif isinstance(expire, timedelta):
            expiration = time.time() + expire.total_seconds()
        else:
            expiration = time.time() + expire
        
        self._cache[key] = (value, expiration)
    
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """
        Get a value from the cache.
        
        Args:
            key (str): The key to retrieve the value for.
            default (Optional[T], optional): The default value to return if the key
                doesn't exist or has expired. Defaults to None.
        
        Returns:
            Optional[T]: The cached value, or the default value if the key doesn't
                exist or has expired.
        """
        if not self.exists(key):
            return default
        
        value, _ = self._cache[key]
        return value
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache and hasn't expired.
        
        Args:
            key (str): The key to check.
        
        Returns:
            bool: True if the key exists and hasn't expired, False otherwise.
        """
        if key not in self._cache:
            return False
        
        _, expiration = self._cache[key]
        if expiration is not None and expiration < time.time():
            # Key has expired, remove it
            del self._cache[key]
            return False
        
        return True
    
    def invalidate(self, key: str) -> None:
        """
        Invalidate a key in the cache.
        
        Args:
            key (str): The key to invalidate.
        """
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

# Create a global cache instance for convenience
cache = Cache()