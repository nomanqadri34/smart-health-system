"""
Comprehensive test suite for alert_dispatcher
"""
import pytest
import json
from datetime import datetime
from alert_dispatcher import AlertDispatcher

def test_init_default():
    """Test default initialization"""
    obj = AlertDispatcher()
    assert obj.data == {}
    assert obj.is_active is True
    assert obj.stats["total"] == 0

def test_init_with_config():
    """Test initialization with config"""
    config = {"setting": "value"}
    obj = AlertDispatcher(config=config)
    assert obj.config == config

def test_process_valid_data():
    """Test processing valid data"""
    obj = AlertDispatcher()
    result = obj.process({"key": "value"})
    assert result["status"] == "success"
    assert obj.stats["success"] == 1

def test_process_invalid_empty():
    """Test processing empty data"""
    obj = AlertDispatcher()
    result = obj.process({})
    assert result["status"] == "error"
    assert obj.stats["errors"] == 1

def test_process_invalid_type():
    """Test processing invalid type"""
    obj = AlertDispatcher()
    result = obj.process("not a dict")
    assert result["status"] == "error"

def test_validate_valid():
    """Test validation with valid data"""
    obj = AlertDispatcher()
    assert obj.validate({"key": "value"}) is True

def test_validate_empty():
    """Test validation with empty dict"""
    obj = AlertDispatcher()
    assert obj.validate({}) is False

def test_validate_non_dict():
    """Test validation with non-dict"""
    obj = AlertDispatcher()
    assert obj.validate("string") is False
    assert obj.validate(123) is False

def test_get_stats():
    """Test getting statistics"""
    obj = AlertDispatcher()
    obj.process({"key": "value"})
    stats = obj.get_stats()
    assert "processing_stats" in stats
    assert stats["processing_stats"]["total"] == 1

def test_success_rate():
    """Test success rate calculation"""
    obj = AlertDispatcher()
    obj.process({"key": "value"})
    obj.process({})
    stats = obj.get_stats()
    assert stats["success_rate"] == 0.5

def test_reset():
    """Test reset functionality"""
    obj = AlertDispatcher()
    obj.data = {"test": "data"}
    obj.stats["total"] = 10
    obj.reset()
    assert obj.data == {}
    assert obj.stats["total"] == 0

def test_configure():
    """Test configuration update"""
    obj = AlertDispatcher()
    result = obj.configure({"new_setting": "new_value"})
    assert result is True
    assert "new_setting" in obj.config

def test_export_data():
    """Test data export"""
    obj = AlertDispatcher()
    obj.data = {"exported": "data"}
    exported = obj.export_data()
    assert isinstance(exported, str)
    assert "exported" in exported

def test_import_data_valid():
    """Test importing valid JSON"""
    obj = AlertDispatcher()
    result = obj.import_data('{"imported": "data"}')
    assert result is True
    assert obj.data["imported"] == "data"

def test_import_data_invalid():
    """Test importing invalid JSON"""
    obj = AlertDispatcher()
    result = obj.import_data("invalid json")
    assert result is False

def test_health_check():
    """Test health check"""
    obj = AlertDispatcher()
    health = obj.health_check()
    assert "healthy" in health
    assert health["healthy"] is True
    assert "uptime" in health
