"""
Config for load distributor
"""

DEFAULT_CONFIG = {
    "enabled": True,
    "max_retries": 3,
    "timeout": 30,
    "log_level": "INFO"
}

PRODUCTION_CONFIG = {
    "enabled": True,
    "max_retries": 5,
    "timeout": 60,
    "log_level": "WARNING"
}

def get_config(env="default"):
    return PRODUCTION_CONFIG if env == "production" else DEFAULT_CONFIG
