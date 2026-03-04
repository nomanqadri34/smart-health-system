"""
Tests for content classifier
"""
import pytest
from content_classifier import ContentClassifier, ContentCategory

def test_classifier_init():
    """Test classifier initialization"""
    classifier = ContentClassifier()
    assert classifier.keywords is not None
    assert "medical" in classifier.keywords

def test_classify_medical():
    """Test medical content classification"""
    classifier = ContentClassifier()
    result = classifier.classify("I have a symptom of fever")
    assert result == ContentCategory.MEDICAL

def test_classify_emergency():
    """Test emergency content classification"""
    classifier = ContentClassifier()
    result = classifier.classify("This is an urgent emergency")
    assert result == ContentCategory.EMERGENCY

def test_classify_wellness():
    """Test wellness content classification"""
    classifier = ContentClassifier()
    result = classifier.classify("I need exercise and diet advice")
    assert result == ContentCategory.WELLNESS

def test_classify_general():
    """Test general content classification"""
    classifier = ContentClassifier()
    result = classifier.classify("Hello, how are you?")
    assert result == ContentCategory.GENERAL

def test_get_priority_emergency():
    """Test priority for emergency"""
    classifier = ContentClassifier()
    priority = classifier.get_priority(ContentCategory.EMERGENCY)
    assert priority == 1

def test_get_priority_medical():
    """Test priority for medical"""
    classifier = ContentClassifier()
    priority = classifier.get_priority(ContentCategory.MEDICAL)
    assert priority == 2

def test_batch_classify():
    """Test batch classification"""
    classifier = ContentClassifier()
    texts = ["I have a symptom", "This is urgent", "Hello"]
    results = classifier.batch_classify(texts)
    assert len(results) == 3
    assert results[0]["category"] == "medical"
    assert results[1]["category"] == "emergency"

def test_batch_classify_empty():
    """Test batch classification with empty list"""
    classifier = ContentClassifier()
    results = classifier.batch_classify([])
    assert results == []
