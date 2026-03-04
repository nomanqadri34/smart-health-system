"""
Content classification and categorization system
"""
from typing import List, Dict, Optional
from enum import Enum

class ContentCategory(Enum):
    """Content categories"""
    MEDICAL = "medical"
    GENERAL = "general"
    EMERGENCY = "emergency"
    WELLNESS = "wellness"

class ContentClassifier:
    """Classify and categorize content"""
    
    def __init__(self):
        self.keywords = {
            "medical": ["symptom", "diagnosis", "treatment", "medication"],
            "emergency": ["urgent", "emergency", "critical", "severe"],
            "wellness": ["exercise", "diet", "nutrition", "fitness"]
        }
    
    def classify(self, text: str) -> ContentCategory:
        """Classify text into category"""
        text_lower = text.lower()
        
        for keyword in self.keywords["emergency"]:
            if keyword in text_lower:
                return ContentCategory.EMERGENCY
        
        for keyword in self.keywords["medical"]:
            if keyword in text_lower:
                return ContentCategory.MEDICAL
        
        for keyword in self.keywords["wellness"]:
            if keyword in text_lower:
                return ContentCategory.WELLNESS
        
        return ContentCategory.GENERAL
    
    def get_priority(self, category: ContentCategory) -> int:
        """Get priority level for category"""
        priorities = {
            ContentCategory.EMERGENCY: 1,
            ContentCategory.MEDICAL: 2,
            ContentCategory.WELLNESS: 3,
            ContentCategory.GENERAL: 4
        }
        return priorities.get(category, 4)
    
    def batch_classify(self, texts: List[str]) -> List[Dict]:
        """Classify multiple texts"""
        results = []
        for text in texts:
            category = self.classify(text)
            results.append({
                "text": text,
                "category": category.value,
                "priority": self.get_priority(category)
            })
        return results
