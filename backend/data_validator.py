"""Data validation and sanitization"""
from typing import Any, Dict, List
import re

class DataValidator:
    def __init__(self):
        self.rules = {}
    
    def validate_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def validate_phone(self, phone: str) -> bool:
        pattern = r'^\+?1?\d{9,15}$'
        return bool(re.match(pattern, phone))
    
    def validate_age(self, age: int) -> bool:
        return 0 < age < 150
    
    def sanitize_text(self, text: str) -> str:
        return text.strip().replace("<", "").replace(">", "")
    
    def validate_dict(self, data: Dict, required_keys: List[str]) -> bool:
        return all(key in data for key in required_keys)
