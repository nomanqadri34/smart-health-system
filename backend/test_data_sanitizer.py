"""Tests for data sanitizer"""
import pytest
from data_sanitizer import DataSanitizer

def test_sanitize_html():
    sanitizer = DataSanitizer()
    result = sanitizer.sanitize_html("<script>alert()</script>")
    assert "<script>" not in result

def test_sanitize_sql():
    sanitizer = DataSanitizer()
    result = sanitizer.sanitize_sql("SELECT * FROM users; DROP TABLE users;")
    assert ";" not in result

def test_sanitize_dict():
    sanitizer = DataSanitizer()
    data = {"name": "<script>", "value": "test"}
    result = sanitizer.sanitize_dict(data)
    assert "<script>" not in str(result)

def test_remove_special_chars():
    sanitizer = DataSanitizer()
    result = sanitizer.remove_special_chars("Hello@#$World!")
    assert result == "HelloWorld"
