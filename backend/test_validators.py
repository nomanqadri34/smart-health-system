"""
Unit tests for input validators.
Tests for issue #1: Add comprehensive validation system
"""
import pytest
from datetime import datetime, timedelta
from validators import (
    validate_symptom_input,
    validate_email,
    validate_phone_number,
    validate_appointment_date,
    validate_user_data
)


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


class TestAppointmentDateValidation:
    """Test cases for appointment date validation."""
    
    def test_valid_future_date(self):
        """Test that valid future date passes validation."""
        future_date = (datetime.now() + timedelta(days=7)).date().isoformat()
        is_valid, error = validate_appointment_date(future_date)
        assert is_valid is True
        assert error is None
    
    def test_past_date(self):
        """Test that past date fails validation."""
        past_date = (datetime.now() - timedelta(days=1)).date().isoformat()
        is_valid, error = validate_appointment_date(past_date)
        assert is_valid is False
        assert "must be in the future" in error
    
    def test_too_far_future(self):
        """Test that date too far in future fails validation."""
        far_future = (datetime.now() + timedelta(days=400)).date().isoformat()
        is_valid, error = validate_appointment_date(far_future)
        assert is_valid is False
        assert "cannot be more than" in error
    
    def test_invalid_format(self):
        """Test that invalid date format fails validation."""
        is_valid, error = validate_appointment_date("invalid-date")
        assert is_valid is False
        assert "Invalid date format" in error
    
    def test_empty_date(self):
        """Test that empty date fails validation."""
        is_valid, error = validate_appointment_date("")
        assert is_valid is False
        assert "cannot be empty" in error


class TestUserDataValidation:
    """Test cases for complete user data validation."""
    
    def test_valid_user_data(self):
        """Test that valid user data passes validation."""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "1234567890"
        }
        is_valid, errors = validate_user_data(data)
        assert is_valid is True
        assert errors is None
    
    def test_missing_name(self):
        """Test that missing name fails validation."""
        data = {
            "email": "john@example.com"
        }
        is_valid, errors = validate_user_data(data)
        assert is_valid is False
        assert "name" in errors
    
    def test_short_name(self):
        """Test that too short name fails validation."""
        data = {
            "name": "J",
            "email": "john@example.com"
        }
        is_valid, errors = validate_user_data(data)
        assert is_valid is False
        assert "name" in errors
    
    def test_invalid_email_in_user_data(self):
        """Test that invalid email in user data fails validation."""
        data = {
            "name": "John Doe",
            "email": "invalid-email"
        }
        is_valid, errors = validate_user_data(data)
        assert is_valid is False
        assert "email" in errors
    
    def test_optional_phone(self):
        """Test that phone is optional."""
        data = {
            "name": "John Doe",
            "email": "john@example.com"
        }
        is_valid, errors = validate_user_data(data)
        assert is_valid is True
    
    def test_invalid_phone_in_user_data(self):
        """Test that invalid phone in user data fails validation."""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "123"
        }
        is_valid, errors = validate_user_data(data)
        assert is_valid is False
        assert "phone" in errors
