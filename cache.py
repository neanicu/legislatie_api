"""
Cache implementation for Legislatie API Client.
Supports both in-memory and persistent disk-based caching.
"""

import time
import hashlib
import pickle
import os
from typing import Any, Optional
import logging

try:
    import diskcache

    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False

logger = logging.getLogger(__name__)


class LegislatieCache:
    """Cache manager for search results."""

    def __init__(
        self,
        use_persistent: bool = False,
        cache_dir: str = "./.legislatie_cache",
        ttl: int = 3600,
    ):
        """
        Initialize cache.

        Args:
            use_persistent: Whether to use persistent disk cache
            cache_dir: Directory for persistent cache (if enabled)
            ttl: Time-to-live in seconds
        """
        self.ttl = ttl

        if use_persistent and DISKCACHE_AVAILABLE:
            self._cache_type = "diskcache"
            os.makedirs(cache_dir, exist_ok=True)
            self._cache = diskcache.Cache(cache_dir)
            logger.info(f"Initialized persistent cache at {cache_dir}")
        else:
            self._cache_type = "memory"
            self._cache = {}
            if use_persistent and not DISKCACHE_AVAILABLE:
                logger.warning(
                    "diskcache not available, falling back to in-memory cache"
                )
            else:
                logger.info("Using in-memory cache")

    def _generate_key(self, *args, **kwargs) -> str:
        """
        Generate a cache key from search parameters.
        Uses SHA256 hash of pickled parameters.
        """
        # Create a stable representation of parameters
        params = {
            "args": args,
            "kwargs": {k: v for k, v in kwargs.items() if v is not None},
        }

        # Sort kwargs for consistent key generation
        params["kwargs"] = dict(sorted(params["kwargs"].items()))

        # Pickle and hash
        pickled = pickle.dumps(params, protocol=pickle.HIGHEST_PROTOCOL)
        return hashlib.sha256(pickled).hexdigest()

    def generate_search_key(
        self,
        numar_pagina=0,
        rezultate_pagina=10,
        an=None,
        numar=None,
        text=None,
        titlu=None,
    ) -> str:
        """
        Generate a cache key for search parameters.
        """
        return self._generate_key(
            numar_pagina=numar_pagina,
            rezultate_pagina=rezultate_pagina,
            an=an,
            numar=numar,
            text=text,
            titlu=titlu,
        )

    def get(self, key: str) -> Optional[Any]:
        """Retrieve item from cache if not expired."""
        try:
            if self._cache_type == "diskcache":
                if key not in self._cache:
                    return None
                item = self._cache[key]
            else:
                item = self._cache.get(key)

            if not item:
                return None

            timestamp, value = item
            if time.time() - timestamp < self.ttl:
                logger.debug(f"Cache hit for key {key[:16]}...")
                return value
            else:
                # Expired, remove from cache
                self.delete(key)
                logger.debug(f"Cache expired for key {key[:16]}...")
                return None
        except Exception as e:
            logger.warning(f"Error retrieving from cache: {e}")
            return None

    def set(self, key: str, value: Any) -> bool:
        """Store item in cache with current timestamp."""
        try:
            item = (time.time(), value)
            if self._cache_type == "diskcache":
                self._cache[key] = item
            else:
                self._cache[key] = item
            logger.debug(f"Cache set for key {key[:16]}...")
            return True
        except Exception as e:
            logger.warning(f"Error storing in cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete item from cache."""
        try:
            if self._cache_type == "diskcache":
                if key in self._cache:
                    del self._cache[key]
            else:
                self._cache.pop(key, None)
            return True
        except Exception as e:
            logger.warning(f"Error deleting from cache: {e}")
            return False

    def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            if self._cache_type == "diskcache":
                self._cache.clear()
            else:
                self._cache.clear()
            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")
            return False

    def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            size = len(self._cache)
            disk_size = None

            if self._cache_type == "diskcache":
                # Estimate disk size
                try:
                    import shutil

                    total, used, free = shutil.disk_usage(self._cache.directory)
                    disk_size = total
                except (AttributeError, ImportError):
                    pass

            return {
                "type": self._cache_type,
                "size": size,
                "ttl": self.ttl,
                "disk_size": disk_size,
            }
        except Exception as e:
            logger.warning(f"Error getting cache stats: {e}")
            return {"error": str(e)}


# Default cache instance
_default_cache = None


def get_cache(
    use_persistent: bool = False,
    cache_dir: str = "./.legislatie_cache",
    ttl: int = 3600,
) -> LegislatieCache:
    """Get or create default cache instance."""
    global _default_cache
    if _default_cache is None:
        _default_cache = LegislatieCache(
            use_persistent=use_persistent, cache_dir=cache_dir, ttl=ttl
        )
    return _default_cache
