"""
Configuration file for notification queue
"""

# Default configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "max_retries": 3,
    "timeout_seconds": 30,
    "log_level": "INFO",
    "cache_enabled": True,
    "batch_size": 100
}

# Production configuration
PRODUCTION_CONFIG = {
    "enabled": True,
    "max_retries": 5,
    "timeout_seconds": 60,
    "log_level": "WARNING",
    "cache_enabled": True,
    "batch_size": 500
}

# Development configuration
DEVELOPMENT_CONFIG = {
    "enabled": True,
    "max_retries": 1,
    "timeout_seconds": 10,
    "log_level": "DEBUG",
    "cache_enabled": False,
    "batch_size": 10
}

def get_config(environment="default"):
    """Get configuration for specified environment"""
    configs = {
        "default": DEFAULT_CONFIG,
        "production": PRODUCTION_CONFIG,
        "development": DEVELOPMENT_CONFIG
    }
    return configs.get(environment, DEFAULT_CONFIG)
