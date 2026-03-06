"""
Helper utilities for backup scheduler
"""
from typing import Dict, List, Any, Optional
from datetime import datetime

def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format datetime as ISO string"""
    if dt is None:
        dt = datetime.now()
    return dt.isoformat()

def validate_dict_keys(data: Dict, required_keys: List[str]) -> bool:
    """Validate dictionary has required keys"""
    return all(key in data for key in required_keys)

def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """Merge two dictionaries"""
    result = dict1.copy()
    result.update(dict2)
    return result

def filter_none_values(data: Dict) -> Dict:
    """Remove None values from dictionary"""
    return {k: v for k, v in data.items() if v is not None}

def calculate_percentage(part: int, total: int) -> float:
    """Calculate percentage safely"""
    if total == 0:
        return 0.0
    return (part / total) * 100

def truncate_string(text: str, max_length: int = 100) -> str:
    """Truncate string to max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def safe_divide(numerator: float, denominator: float) -> float:
    """Safely divide two numbers"""
    if denominator == 0:
        return 0.0
    return numerator / denominator
