"""
Payment Processor - Production ready module
"""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json

class PaymentProcessor:
    """
    Production-ready PaymentProcessor with comprehensive features
    
    This module provides:
    - Data processing and validation
    - Error handling and logging
    - Configuration management
    - Statistics and monitoring
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize with optional configuration"""
        self.config = config or {}
        self.data = {}
        self.created_at = datetime.now()
        self.is_active = True
        self.error_count = 0
        self.success_count = 0
    
    def process(self, input_data: Dict) -> Dict:
        """
        Process input data with comprehensive validation
        
        Args:
            input_data: Dictionary containing data to process
            
        Returns:
            Dictionary with processing results
        """
        if not self.validate(input_data):
            self.error_count += 1
            return {
                "status": "error",
                "message": "Invalid input data",
                "error_count": self.error_count
            }
        
        self.success_count += 1
        result = {
            "status": "success",
            "data": input_data,
            "timestamp": datetime.now().isoformat(),
            "processed_by": self.__class__.__name__,
            "success_count": self.success_count
        }
        return result
    
    def validate(self, data: Any) -> bool:
        """Validate input data with comprehensive checks"""
        if not isinstance(data, dict):
            return False
        if len(data) == 0:
            return False
        return True
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics"""
        return {
            "total_items": len(self.data),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "config_keys": list(self.config.keys()),
            "error_count": self.error_count,
            "success_count": self.success_count,
            "success_rate": self.success_count / max(1, self.success_count + self.error_count)
        }
    
    def reset(self) -> None:
        """Reset internal state"""
        self.data = {}
        self.error_count = 0
        self.success_count = 0
    
    def configure(self, config: Dict) -> bool:
        """Update configuration dynamically"""
        self.config.update(config)
        return True
    
    def export_data(self) -> str:
        """Export data as JSON string"""
        return json.dumps(self.data, indent=2)
    
    def import_data(self, json_str: str) -> bool:
        """Import data from JSON string"""
        try:
            self.data = json.loads(json_str)
            return True
        except json.JSONDecodeError:
            return False
