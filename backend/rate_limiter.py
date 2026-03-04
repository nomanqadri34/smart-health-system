"""
Rate limiting system for API requests
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

class RateLimiter:
    """Rate limiter with sliding window"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # Remove old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]
        
        # Check limit
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # Add new request
        self.requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # Count recent requests
        recent = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]
        
        return max(0, self.max_requests - len(recent))
    
    def reset(self, client_id: str) -> None:
        """Reset rate limit for client"""
        if client_id in self.requests:
            del self.requests[client_id]
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics"""
        return {
            "total_clients": len(self.requests),
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds
        }
