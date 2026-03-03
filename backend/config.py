"""
Configuration settings for Smart Health API.
Part of issue #1: Add comprehensive validation system
"""
import os
from typing import Optional


class ValidationConfig:
    """Configuration for validation rules."""
    
    # Symptom validation
    MIN_SYMPTOM_LENGTH = 3
    MAX_SYMPTOM_LENGTH = 500
    
    # Email validation
    MAX_EMAIL_LENGTH = 254
    
    # Phone validation
    MIN_PHONE_DIGITS = 10
    MAX_PHONE_DIGITS = 15
    
    # Name validation
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 100
    
    # Appointment validation
    MAX_APPOINTMENT_DAYS_FUTURE = 365
    
    # Security
    ENABLE_XSS_PROTECTION = True
    ENABLE_SQL_INJECTION_PROTECTION = True


class APIConfig:
    """Configuration for API settings."""
    
    # API Settings
    API_TITLE = "Smart Health API"
    API_VERSION = "1.0.0"
    API_DESCRIPTION = "AI-powered health appointment system"
    
    # CORS Settings
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_METHODS = ["*"]
    CORS_ALLOW_HEADERS = ["*"]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class DatabaseConfig:
    """Configuration for database settings."""
    
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")
    DATABASE_ECHO = os.getenv("DATABASE_ECHO", "False").lower() == "true"
    
    # Connection pool settings
    POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
    MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))


class SecurityConfig:
    """Configuration for security settings."""
    
    # JWT Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Password Settings
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL_CHAR = True
    
    # Session Settings
    SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))


# Create singleton instances
validation_config = ValidationConfig()
api_config = APIConfig()
database_config = DatabaseConfig()
security_config = SecurityConfig()
