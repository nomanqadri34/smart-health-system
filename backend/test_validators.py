"""
Unit tests for input validators.
Tests for issue #1: Add input validation for symptom analysis
"""
import pytest
from validators import validate_symptom_input, validate_email, validate_phone_number


class TestSymptomValidation:
    """Test cases for symptom input validation."""
    
    def test_valid_symptom(self):
        """Test that valid symptom text passes validation."""
        is_valid, error = validate_symptom_input("I have a severe headache")
        assert is_valid is True
        assert error is None
    
    def test_empty_symptom(self):
        """Test that empty symptom text fails validation."""
        is_valid, error = validate_symptom_input("")
        assert is_valid is False
        assert "cannot be empty" in error
    
    def test_none_symptom(self):
        """Test that None symptom text fails validation."""
        is_valid, error = validate_symptom_input(None)
        assert is_valid is False
        assert "cannot be empty" in error
    
    def test_short_symptom(self):
        """Test that too short symptom text fails validation."""
        is_valid, error = validate_symptom_input("ab")
        assert is_valid is False
        assert "at least 3 characters" in error
    
    def test_long_symptom(self):
        """Test that too long symptom text fails validation."""
        long_text = "a" * 501
        is_valid, error = validate_symptom_input(long_text)
        assert is_valid is False
        assert "must not exceed 500 characters" in error
    
    def test_xss_attempt(self):
        """Test that XSS attempts are blocked."""
        is_valid, error = validate_symptom_input("<script>alert('xss')</script>")
        assert is_valid is False
        assert "Invalid characters" in error
    
    def test_javascript_injection(self):
        """Test that JavaScript injection attempts are blocked."""
        is_valid, error = validate_symptom_input("javascript:alert('test')")
        assert is_valid is False
        assert "Invalid characters" in error


class TestEmailValidation:
    """Test cases for email validation."""
    
    def test_valid_email(self):
        """Test that valid email passes validation."""
        is_valid, error = validate_email("user@example.com")
        assert is_valid is True
        assert error is None
    
    def test_empty_email(self):
        """Test that empty email fails validation."""
        is_valid, error = validate_email("")
        assert is_valid is False
        assert "cannot be empty" in error
    
    def test_invalid_format(self):
        """Test that invalid email format fails validation."""
        is_valid, error = validate_email("invalid-email")
        assert is_valid is False
        assert "Invalid email format" in error
    
    def test_missing_domain(self):
        """Test that email without domain fails validation."""
        is_valid, error = validate_email("user@")
        assert is_valid is False
        assert "Invalid email format" in error
    
    def test_too_long_email(self):
        """Test that too long email fails validation."""
        long_email = "a" * 250 + "@test.com"
        is_valid, error = validate_email(long_email)
        assert is_valid is False
        assert "too long" in error


class TestPhoneValidation:
    """Test cases for phone number validation."""
    
    def test_valid_phone(self):
        """Test that valid phone number passes validation."""
        is_valid, error = validate_phone_number("1234567890")
        assert is_valid is True
        assert error is None
    
    def test_valid_phone_with_formatting(self):
        """Test that formatted phone number passes validation."""
        is_valid, error = validate_phone_number("+1 (234) 567-8900")
        assert is_valid is True
        assert error is None
    
    def test_empty_phone(self):
        """Test that empty phone fails validation."""
        is_valid, error = validate_phone_number("")
        assert is_valid is False
        assert "cannot be empty" in error
    
    def test_phone_with_letters(self):
        """Test that phone with letters fails validation."""
        is_valid, error = validate_phone_number("123abc7890")
        assert is_valid is False
        assert "must contain only digits" in error
    
    def test_too_short_phone(self):
        """Test that too short phone fails validation."""
        is_valid, error = validate_phone_number("123456")
        assert is_valid is False
        assert "between 10 and 15 digits" in error
    
    def test_too_long_phone(self):
        """Test that too long phone fails validation."""
        is_valid, error = validate_phone_number("1234567890123456")
        assert is_valid is False
        assert "between 10 and 15 digits" in error
