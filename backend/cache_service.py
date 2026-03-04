"""
Caching service for performance optimization
"""
from typing import Any, Optional
from datetime import datetime, timedelta
import json

class CacheService:
    """In-memory cache with TTL support"""
    
    def __init__(self):
        self._cache = {}
        self._expiry = {}
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Set cache value with TTL"""
        try:
            self._cache[key] = value
            self._expiry[key] = datetime.now() + timedelta(seconds=ttl_seconds)
            return True
        except Exception:
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get cache value if not expired"""
        if key not in self._cache:
            return None
        
        if datetime.now() > self._expiry[key]:
            self.delete(key)
            return None
        
        return self._cache[key]
    
    def delete(self, key: str) -> bool:
        """Delete cache entry"""
        if key in self._cache:
            del self._cache[key]
            del self._expiry[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache"""
        self._cache.clear()
        self._expiry.clear()
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = len(self._cache)
        expired = sum(1 for k in self._cache if datetime.now() > self._expiry[k])
        return {"total": total, "expired": expired, "active": total - expired}
