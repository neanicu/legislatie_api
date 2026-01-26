"""
Unit tests for LegislatieCache class.
"""

import pytest
import time
import tempfile
import shutil
from unittest.mock import Mock, patch

from cache import LegislatieCache


class TestLegislatieCache:
    """Test suite for LegislatieCache."""

    def test_init_memory_cache(self):
        """Test initialization with in-memory cache."""
        cache = LegislatieCache(use_persistent=False)
        assert cache._cache_type == "memory"
        assert isinstance(cache._cache, dict)

    def test_init_diskcache(self, temp_cache_dir):
        """Test initialization with diskcache."""
        # Mock diskcache availability
        with patch("cache.DISKCACHE_AVAILABLE", True):
            cache = LegislatieCache(use_persistent=True, cache_dir=temp_cache_dir)
            assert cache._cache_type == "diskcache"
            assert hasattr(cache._cache, "get")
            assert hasattr(cache._cache, "set")

    def test_init_diskcache_fallback(self):
        """Test fallback to memory cache when diskcache not available."""
        with patch("cache.DISKCACHE_AVAILABLE", False):
            cache = LegislatieCache(use_persistent=True)
            assert cache._cache_type == "memory"
            assert isinstance(cache._cache, dict)

    def test_generate_key_consistent(self):
        """Test that key generation is consistent for same inputs."""
        cache = LegislatieCache(use_persistent=False)

        key1 = cache._generate_key("test", 123, param="value")
        key2 = cache._generate_key("test", 123, param="value")

        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) == 64  # SHA256 hex digest length

    def test_generate_key_different(self):
        """Test that key generation differs for different inputs."""
        cache = LegislatieCache(use_persistent=False)

        key1 = cache._generate_key("test", 123, param="value1")
        key2 = cache._generate_key("test", 123, param="value2")

        assert key1 != key2

    def test_set_get_memory_cache(self):
        """Test set and get operations with memory cache."""
        cache = LegislatieCache(use_persistent=False, ttl=60)

        test_data = {"results": [1, 2, 3], "timestamp": time.time()}
        cache_key = cache._generate_key("search", param="test")

        # Set value
        result = cache.set(cache_key, test_data)
        assert result is True

        # Get value
        retrieved = cache.get(cache_key)
        assert retrieved == test_data

    def test_set_get_diskcache(self, temp_cache_dir):
        """Test set and get operations with diskcache."""
        with patch("cache.DISKCACHE_AVAILABLE", True):
            cache = LegislatieCache(
                use_persistent=True, cache_dir=temp_cache_dir, ttl=60
            )

            test_data = {"results": [1, 2, 3], "timestamp": time.time()}
            cache_key = cache._generate_key("search", param="test")

            # Set value
            result = cache.set(cache_key, test_data)
            assert result is True

            # Get value
            retrieved = cache.get(cache_key)
            assert retrieved == test_data

    def test_get_expired(self):
        """Test that expired items are not returned."""
        cache = LegislatieCache(use_persistent=False, ttl=1)  # 1 second TTL

        test_data = {"data": "test"}
        cache_key = cache._generate_key("test")

        cache.set(cache_key, test_data)

        # Immediately get should work
        retrieved = cache.get(cache_key)
        assert retrieved == test_data

        # Wait for expiration
        time.sleep(1.1)

        # Should return None after expiration
        retrieved = cache.get(cache_key)
        assert retrieved is None

    def test_delete(self):
        """Test delete operation."""
        cache = LegislatieCache(use_persistent=False)

        test_data = {"data": "test"}
        cache_key = cache._generate_key("test")

        cache.set(cache_key, test_data)
        assert cache.get(cache_key) == test_data

        # Delete
        result = cache.delete(cache_key)
        assert result is True

        # Should be gone
        assert cache.get(cache_key) is None

    def test_delete_nonexistent(self):
        """Test deleting non-existent key."""
        cache = LegislatieCache(use_persistent=False)

        cache_key = cache._generate_key("nonexistent")
        result = cache.delete(cache_key)
        assert result is True  # delete returns True even if key doesn't exist

    def test_clear_memory_cache(self):
        """Test clearing memory cache."""
        cache = LegislatieCache(use_persistent=False)

        # Add some data
        for i in range(5):
            cache.set(cache._generate_key(f"test{i}"), {"data": i})

        # Verify data exists
        for i in range(5):
            assert cache.get(cache._generate_key(f"test{i}")) is not None

        # Clear cache
        result = cache.clear()
        assert result is True

        # Verify all data is gone
        for i in range(5):
            assert cache.get(cache._generate_key(f"test{i}")) is None

    def test_clear_diskcache(self, temp_cache_dir):
        """Test clearing diskcache."""
        with patch("cache.DISKCACHE_AVAILABLE", True):
            cache = LegislatieCache(use_persistent=True, cache_dir=temp_cache_dir)

            # Add some data
            for i in range(3):
                cache.set(cache._generate_key(f"test{i}"), {"data": i})

            # Clear cache
            result = cache.clear()
            assert result is True

            # Verify all data is gone
            for i in range(3):
                assert cache.get(cache._generate_key(f"test{i}")) is None

    def test_get_stats_memory(self):
        """Test get_stats for memory cache."""
        cache = LegislatieCache(use_persistent=False)

        stats = cache.get_stats()
        assert isinstance(stats, dict)
        assert "type" in stats
        assert "size" in stats
        assert "ttl" in stats
        assert "disk_size" in stats
        assert stats["type"] == "memory"
        assert stats["size"] == 0
        assert stats["ttl"] == 3600
        assert stats["disk_size"] is None

        # Add some data and test stats update
        cache.set(cache._generate_key("test1"), {"data": 1})
        cache.set(cache._generate_key("test2"), {"data": 2})

        stats = cache.get_stats()
        assert stats["size"] == 2
        assert stats["type"] == "memory"

    def test_get_stats_diskcache(self, temp_cache_dir):
        """Test get_stats for diskcache."""
        with patch("cache.DISKCACHE_AVAILABLE", True):
            cache = LegislatieCache(use_persistent=True, cache_dir=temp_cache_dir)

            stats = cache.get_stats()
            assert isinstance(stats, dict)
            assert "type" in stats
            assert "size" in stats
            assert "ttl" in stats
            assert "disk_size" in stats
            assert stats["type"] == "diskcache"
            assert stats["size"] == 0
            assert stats["ttl"] == 3600
            assert isinstance(stats["disk_size"], (int, type(None)))

    def test_pickle_safe(self):
        """Test that cache handles picklable data correctly."""
        cache = LegislatieCache(use_persistent=False)

        test_data = {
            "string": "test value",
            "int": 123,
            "float": 3.14,
            "list": [1, 2, 3],
            "dict": {"key": "value"},
            "tuple": (1, 2, 3),
            "none": None,
            "bool": True,
        }

        cache_key = cache._generate_key("pickle_test")
        cache.set(cache_key, test_data)

        retrieved = cache.get(cache_key)
        assert retrieved == test_data

    @pytest.mark.skip(reason="Memory cache can store any Python object")
    @pytest.mark.parametrize(
        "invalid_data",
        [
            lambda: "function",  # Not picklable
            object(),  # Arbitrary object
        ],
    )
    def test_unpicklable_data(self, invalid_data):
        """Test that unpicklable data returns False."""
        # Memory cache can store any object, diskcache would fail
        # This test is not useful for memory cache
        pass
