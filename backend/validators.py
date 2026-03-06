"""
Input validation utilities for Smart Health API.
Fixes issue #1: Add input validation for symptom analysis
"""
import re
from typing import Optional, Tuple


def validate_symptom_input(symptom_text: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate symptom input text.
    
    Args:
        symptom_text: The symptom description from user
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not symptom_text:
        return False, "Symptom text cannot be empty"
    
    if len(symptom_text.strip()) < 3:
        return False, "Symptom description must be at least 3 characters"
    
    if len(symptom_text) > 500:
        return False, "Symptom description must not exceed 500 characters"
    
    # Check for potentially malicious input
    dangerous_patterns = [
        r'<script',
        r'javascript:',
        r'onerror=',
        r'onclick='
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, symptom_text, re.IGNORECASE):
            return False, "Invalid characters detected in symptom description"
    
    return True, None


def validate_email(email: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email cannot be empty"
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    if len(email) > 254:
        return False, "Email address too long"
    
    return True, None


def validate_phone_number(phone: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone:
        return False, "Phone number cannot be empty"
    
    # Remove common formatting characters
    cleaned_phone = re.sub(r'[\s\-\(\)\+]', '', phone)
    
    if not cleaned_phone.isdigit():
        return False, "Phone number must contain only digits"
    
    if len(cleaned_phone) < 10 or len(cleaned_phone) > 15:
        return False, "Phone number must be between 10 and 15 digits"
    
    return True, None
