"""
Helpers for encryption manager
"""
from typing import Dict, Any
from datetime import datetime

def format_timestamp(dt=None):
    return (dt or datetime.now()).isoformat()

def validate_keys(data: Dict, keys: list) -> bool:
    return all(k in data for k in keys)

def merge_dicts(d1: Dict, d2: Dict) -> Dict:
    result = d1.copy()
    result.update(d2)
    return result

def filter_none(data: Dict) -> Dict:
    return {k: v for k, v in data.items() if v is not None}
