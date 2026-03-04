"""
Analytics service for tracking and reporting
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

class AnalyticsService:
    """Track and analyze application metrics"""
    
    def __init__(self):
        self.events = []
        self.metrics = defaultdict(int)
    
    def track_event(self, event_type: str, user_id: Optional[str] = None, 
                    metadata: Optional[Dict] = None) -> bool:
        """Track an analytics event"""
        try:
            event = {
                "type": event_type,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            self.events.append(event)
            self.metrics[event_type] += 1
            return True
        except Exception:
            return False
    
    def get_event_count(self, event_type: str) -> int:
        """Get count of specific event type"""
        return self.metrics.get(event_type, 0)
    
    def get_events_by_type(self, event_type: str) -> List[Dict]:
        """Get all events of specific type"""
        return [e for e in self.events if e["type"] == event_type]
    
    def get_events_by_user(self, user_id: str) -> List[Dict]:
        """Get all events for specific user"""
        return [e for e in self.events if e.get("user_id") == user_id]
    
    def get_summary(self) -> Dict:
        """Get analytics summary"""
        return {
            "total_events": len(self.events),
            "event_types": len(self.metrics),
            "metrics": dict(self.metrics)
        }
    
    def clear_events(self) -> None:
        """Clear all events"""
        self.events.clear()
        self.metrics.clear()
