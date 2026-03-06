"""
Tests for cache service
"""
import pytest
import time
from cache_service import CacheService

def test_cache_init():
    """Test cache initialization"""
    cache = CacheService()
    assert cache._cache == {}
    assert cache._expiry == {}

def test_set_and_get():
    """Test setting and getting cache values"""
    cache = CacheService()
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"

def test_get_nonexistent():
    """Test getting non-existent key"""
    cache = CacheService()
    assert cache.get("nonexistent") is None


def test_ttl_expiry():
    """Test TTL expiration"""
    cache = CacheService()
    cache.set("key1", "value1", ttl_seconds=1)
    assert cache.get("key1") == "value1"
    time.sleep(1.1)
    assert cache.get("key1") is None

def test_delete():
    """Test deleting cache entry"""
    cache = CacheService()
    cache.set("key1", "value1")
    assert cache.delete("key1") is True
    assert cache.get("key1") is None

def test_delete_nonexistent():
    """Test deleting non-existent key"""
    cache = CacheService()
    assert cache.delete("nonexistent") is False

def test_clear():
    """Test clearing all cache"""
    cache = CacheService()
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.clear()
    assert cache.get("key1") is None
    assert cache.get("key2") is None

def test_get_stats():
    """Test cache statistics"""
    cache = CacheService()
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    stats = cache.get_stats()
    assert stats["total"] == 2
    assert stats["active"] == 2
