"""
Configuration for pipeline runner
"""

DEFAULT_CONFIG = {
    "enabled": True,
    "max_retries": 3,
    "timeout_seconds": 30,
    "log_level": "INFO",
    "cache_enabled": True,
    "batch_size": 100,
    "retry_delay": 1,
    "max_history_size": 100
}

PRODUCTION_CONFIG = {
    "enabled": True,
    "max_retries": 5,
    "timeout_seconds": 60,
    "log_level": "WARNING",
    "cache_enabled": True,
    "batch_size": 500,
    "retry_delay": 2,
    "max_history_size": 1000
}

DEVELOPMENT_CONFIG = {
    "enabled": True,
    "max_retries": 1,
    "timeout_seconds": 10,
    "log_level": "DEBUG",
    "cache_enabled": False,
    "batch_size": 10,
    "retry_delay": 0.5,
    "max_history_size": 50
}

def get_config(environment="default"):
    """Get configuration for environment"""
    configs = {
        "default": DEFAULT_CONFIG,
        "production": PRODUCTION_CONFIG,
        "development": DEVELOPMENT_CONFIG
    }
    return configs.get(environment, DEFAULT_CONFIG)

def validate_config(config):
    """Validate configuration"""
    required_keys = ["enabled", "max_retries", "timeout_seconds", "log_level"]
    return all(key in config for key in required_keys)

def merge_configs(base_config, override_config):
    """Merge two configurations"""
    result = base_config.copy()
    result.update(override_config)
    return result
