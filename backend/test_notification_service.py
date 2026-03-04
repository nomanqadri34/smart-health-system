"""
Tests for notification service
"""
import pytest
from notification_service import NotificationService

def test_notification_service_init():
    """Test service initialization"""
    service = NotificationService()
    assert service.smtp_host == "smtp.gmail.com"
    assert service.smtp_port == 587

def test_send_email_success():
    """Test email sending"""
    service = NotificationService()
    result = service.send_email("test@example.com", "Test", "Body")
    assert result is True


def test_send_sms_success():
    """Test SMS sending"""
    service = NotificationService()
    result = service.send_sms("+1234567890", "Test message")
    assert result is True

def test_send_sms_invalid_phone():
    """Test SMS with invalid phone"""
    service = NotificationService()
    result = service.send_sms("", "Test")
    assert result is False

def test_send_sms_message_too_long():
    """Test SMS with message > 160 chars"""
    service = NotificationService()
    long_msg = "x" * 161
    result = service.send_sms("+1234567890", long_msg)
    assert result is False

def test_appointment_reminder():
    """Test appointment reminder"""
    service = NotificationService()
    result = service.send_appointment_reminder(
        "test@example.com", "+1234567890", "2026-03-15"
    )
    assert result["email"] is True
    assert result["sms"] is True
