"""
Tests for analytics service
"""
import pytest
from analytics_service import AnalyticsService

def test_analytics_init():
    """Test analytics initialization"""
    analytics = AnalyticsService()
    assert analytics.events == []
    assert len(analytics.metrics) == 0


def test_track_event():
    """Test tracking events"""
    analytics = AnalyticsService()
    result = analytics.track_event("login", "user123")
    assert result is True
    assert len(analytics.events) == 1

def test_track_event_with_metadata():
    """Test tracking event with metadata"""
    analytics = AnalyticsService()
    metadata = {"ip": "192.168.1.1", "device": "mobile"}
    analytics.track_event("login", "user123", metadata)
    assert analytics.events[0]["metadata"] == metadata

def test_get_event_count():
    """Test getting event count"""
    analytics = AnalyticsService()
    analytics.track_event("login", "user1")
    analytics.track_event("login", "user2")
    analytics.track_event("logout", "user1")
    assert analytics.get_event_count("login") == 2
    assert analytics.get_event_count("logout") == 1

def test_get_events_by_type():
    """Test getting events by type"""
    analytics = AnalyticsService()
    analytics.track_event("login", "user1")
    analytics.track_event("logout", "user1")
    analytics.track_event("login", "user2")
    login_events = analytics.get_events_by_type("login")
    assert len(login_events) == 2

def test_get_events_by_user():
    """Test getting events by user"""
    analytics = AnalyticsService()
    analytics.track_event("login", "user1")
    analytics.track_event("logout", "user1")
    analytics.track_event("login", "user2")
    user1_events = analytics.get_events_by_user("user1")
    assert len(user1_events) == 2

def test_get_summary():
    """Test getting analytics summary"""
    analytics = AnalyticsService()
    analytics.track_event("login", "user1")
    analytics.track_event("logout", "user1")
    summary = analytics.get_summary()
    assert summary["total_events"] == 2
    assert summary["event_types"] == 2

def test_clear_events():
    """Test clearing events"""
    analytics = AnalyticsService()
    analytics.track_event("login", "user1")
    analytics.clear_events()
    assert len(analytics.events) == 0
