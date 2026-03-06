"""Tests for data validator"""
import pytest
from data_validator import DataValidator

def test_validate_email_valid():
    validator = DataValidator()
    assert validator.validate_email("test@example.com") is True

def test_validate_email_invalid():
    validator = DataValidator()
    assert validator.validate_email("invalid-email") is False

def test_validate_phone_valid():
    validator = DataValidator()
    assert validator.validate_phone("+1234567890") is True

def test_validate_phone_invalid():
    validator = DataValidator()
    assert validator.validate_phone("123") is False

def test_validate_age_valid():
    validator = DataValidator()
    assert validator.validate_age(25) is True

def test_validate_age_invalid():
    validator = DataValidator()
    assert validator.validate_age(200) is False

def test_sanitize_text():
    validator = DataValidator()
    result = validator.sanitize_text("  <script>alert()</script>  ")
    assert "<" not in result and ">" not in result

def test_validate_dict_valid():
    validator = DataValidator()
    data = {"name": "John", "age": 30}
    assert validator.validate_dict(data, ["name", "age"]) is True

def test_validate_dict_invalid():
    validator = DataValidator()
    data = {"name": "John"}
    assert validator.validate_dict(data, ["name", "age"]) is False
