"""Data sanitization utilities"""
from typing import Any, Dict
import html

class DataSanitizer:
    def __init__(self):
        self.dangerous_chars = ["<", ">", "&", '"', "'"]
    
    def sanitize_html(self, text: str) -> str:
        return html.escape(text)
    
    def sanitize_sql(self, text: str) -> str:
        dangerous = ["'", '"', ";", "--", "/*", "*/"]
        for char in dangerous:
            text = text.replace(char, "")
        return text
    
    def sanitize_dict(self, data: Dict) -> Dict:
        return {k: self.sanitize_html(str(v)) for k, v in data.items()}
    
    def remove_special_chars(self, text: str) -> str:
        return ''.join(c for c in text if c.isalnum() or c.isspace())
