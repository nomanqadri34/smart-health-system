"""
Comprehensive test suite for activity_analyzer
"""
import pytest
import json
from datetime import datetime
from activity_analyzer import ActivityAnalyzer

def test_init_default():
    """Test initialization with default parameters"""
    obj = ActivityAnalyzer()
    assert obj.data == {}
    assert obj.is_active is True
    assert obj.error_count == 0
    assert obj.success_count == 0

def test_init_with_config():
    """Test initialization with custom configuration"""
    config = {"key": "value", "enabled": True}
    obj = ActivityAnalyzer(config=config)
    assert obj.config == config
    assert "key" in obj.config

def test_process_valid_data():
    """Test processing with valid data"""
    obj = ActivityAnalyzer()
    result = obj.process({"key": "value"})
    assert result["status"] == "success"
    assert "timestamp" in result
    assert obj.success_count == 1

def test_process_invalid_empty():
    """Test processing with empty data"""
    obj = ActivityAnalyzer()
    result = obj.process({})
    assert result["status"] == "error"
    assert obj.error_count == 1

def test_process_multiple():
    """Test processing multiple items"""
    obj = ActivityAnalyzer()
    obj.process({"key1": "value1"})
    obj.process({"key2": "value2"})
    assert obj.success_count == 2

def test_validate_valid_dict():
    """Test validation with valid dictionary"""
    obj = ActivityAnalyzer()
    assert obj.validate({"key": "value"}) is True

def test_validate_empty_dict():
    """Test validation with empty dictionary"""
    obj = ActivityAnalyzer()
    assert obj.validate({}) is False

def test_validate_non_dict():
    """Test validation with non-dictionary input"""
    obj = ActivityAnalyzer()
    assert obj.validate("string") is False
    assert obj.validate(123) is False
    assert obj.validate([]) is False

def test_get_stats_initial():
    """Test statistics after initialization"""
    obj = ActivityAnalyzer()
    stats = obj.get_stats()
    assert "total_items" in stats
    assert "is_active" in stats
    assert stats["is_active"] is True
    assert stats["error_count"] == 0

def test_get_stats_after_processing():
    """Test statistics after processing"""
    obj = ActivityAnalyzer()
    obj.process({"key": "value"})
    stats = obj.get_stats()
    assert stats["success_count"] == 1
    assert stats["success_rate"] == 1.0

def test_reset():
    """Test resetting internal state"""
    obj = ActivityAnalyzer()
    obj.data = {"test": "data"}
    obj.success_count = 5
    obj.reset()
    assert obj.data == {}
    assert obj.success_count == 0

def test_configure():
    """Test configuration update"""
    obj = ActivityAnalyzer()
    result = obj.configure({"new_key": "new_value"})
    assert result is True
    assert "new_key" in obj.config

def test_export_data():
    """Test data export"""
    obj = ActivityAnalyzer()
    obj.data = {"key": "value"}
    exported = obj.export_data()
    assert isinstance(exported, str)
    assert "key" in exported

def test_import_data_valid():
    """Test data import with valid JSON"""
    obj = ActivityAnalyzer()
    json_str = '{"imported": "data"}'
    result = obj.import_data(json_str)
    assert result is True
    assert obj.data == {"imported": "data"}

def test_import_data_invalid():
    """Test data import with invalid JSON"""
    obj = ActivityAnalyzer()
    result = obj.import_data("invalid json")
    assert result is False
