"""
Tests for rate limiter
"""
import pytest
import time
from rate_limiter import RateLimiter

def test_rate_limiter_init():
    """Test rate limiter initialization"""
    limiter = RateLimiter(max_requests=10, window_seconds=60)
    assert limiter.max_requests == 10
    assert limiter.window_seconds == 60

def test_is_allowed_first_request():
    """Test first request is allowed"""
    limiter = RateLimiter(max_requests=5)
    assert limiter.is_allowed("client1") is True

def test_is_allowed_within_limit():
    """Test requests within limit"""
    limiter = RateLimiter(max_requests=3)
    assert limiter.is_allowed("client1") is True
    assert limiter.is_allowed("client1") is True
    assert limiter.is_allowed("client1") is True

def test_is_allowed_exceeds_limit():
    """Test request exceeding limit"""
    limiter = RateLimiter(max_requests=2)
    limiter.is_allowed("client1")
    limiter.is_allowed("client1")
    assert limiter.is_allowed("client1") is False

def test_get_remaining():
    """Test getting remaining requests"""
    limiter = RateLimiter(max_requests=5)
    limiter.is_allowed("client1")
    remaining = limiter.get_remaining("client1")
    assert remaining == 4

def test_get_remaining_new_client():
    """Test remaining for new client"""
    limiter = RateLimiter(max_requests=10)
    remaining = limiter.get_remaining("new_client")
    assert remaining == 10

def test_reset():
    """Test resetting client limit"""
    limiter = RateLimiter(max_requests=2)
    limiter.is_allowed("client1")
    limiter.is_allowed("client1")
    limiter.reset("client1")
    assert limiter.is_allowed("client1") is True

def test_get_stats():
    """Test getting statistics"""
    limiter = RateLimiter(max_requests=100, window_seconds=60)
    limiter.is_allowed("client1")
    limiter.is_allowed("client2")
    stats = limiter.get_stats()
    assert stats["total_clients"] == 2
    assert stats["max_requests"] == 100

def test_multiple_clients():
    """Test multiple clients independently"""
    limiter = RateLimiter(max_requests=2)
    assert limiter.is_allowed("client1") is True
    assert limiter.is_allowed("client2") is True
    assert limiter.is_allowed("client1") is True
    assert limiter.is_allowed("client2") is True
