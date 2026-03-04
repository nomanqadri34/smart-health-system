"""
Tests for file_uploader
"""
import pytest
from file_uploader import FileUploader

def test_init():
    obj = FileUploader()
    assert obj.data == {}

def test_process():
    obj = FileUploader()
    result = obj.process({"key": "value"})
    assert result["status"] == "success"

def test_validate_valid():
    obj = FileUploader()
    assert obj.validate({"key": "value"}) is True

def test_validate_invalid():
    obj = FileUploader()
    assert obj.validate({}) is False

def test_get_stats():
    obj = FileUploader()
    stats = obj.get_stats()
    assert "total" in stats
    assert stats["active"] is True
