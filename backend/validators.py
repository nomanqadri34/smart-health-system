"""
Input validation utilities for Smart Health API.
Fixes issue #1: Add comprehensive validation system
"""
import re
from typing import Optional, Tuple, Dict, Any
from datetime import datetime


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


def validate_appointment_date(date_str: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate appointment date.
    
    Args:
        date_str: Date string in ISO format (YYYY-MM-DD)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not date_str:
        return False, "Date cannot be empty"
    
    try:
        appointment_date = datetime.fromisoformat(date_str)
        
        # Check if date is in the future
        if appointment_date.date() < datetime.now().date():
            return False, "Appointment date must be in the future"
        
        # Check if date is not too far in the future (e.g., 1 year)
        max_future_days = 365
        days_diff = (appointment_date.date() - datetime.now().date()).days
        if days_diff > max_future_days:
            return False, f"Appointment date cannot be more than {max_future_days} days in the future"
        
        return True, None
    except ValueError:
        return False, "Invalid date format. Use YYYY-MM-DD"


def validate_user_data(data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, str]]]:
    """
    Validate complete user registration data.
    
    Args:
        data: Dictionary containing user data
        
    Returns:
        Tuple of (is_valid, errors_dict)
    """
    errors = {}
    
    # Validate name
    if 'name' in data:
        name = data['name']
        if not name or len(name.strip()) < 2:
            errors['name'] = "Name must be at least 2 characters"
        elif len(name) > 100:
            errors['name'] = "Name must not exceed 100 characters"
    else:
        errors['name'] = "Name is required"
    
    # Validate email
    if 'email' in data:
        is_valid, error = validate_email(data['email'])
        if not is_valid:
            errors['email'] = error
    else:
        errors['email'] = "Email is required"
    
    # Validate phone (if provided)
    if 'phone' in data and data['phone']:
        is_valid, error = validate_phone_number(data['phone'])
        if not is_valid:
            errors['phone'] = error
    
    return len(errors) == 0, errors if errors else None
