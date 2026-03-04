"""
Tests for report generator
"""
import pytest
import json
from report_generator import ReportGenerator

def test_report_generator_init():
    """Test report generator initialization"""
    generator = ReportGenerator()
    assert generator.reports == []

def test_generate_user_report():
    """Test generating user report"""
    generator = ReportGenerator()
    data = {"logins": 5, "actions": 20}
    report = generator.generate_user_report("user123", data)
    assert report["type"] == "user_activity"
    assert report["user_id"] == "user123"
    assert report["data"] == data

def test_generate_system_report():
    """Test generating system report"""
    generator = ReportGenerator()
    metrics = {"cpu": 45.2, "memory": 60.5}
    report = generator.generate_system_report(metrics)
    assert report["type"] == "system_metrics"
    assert report["metrics"] == metrics

def test_get_report():
    """Test getting report by ID"""
    generator = ReportGenerator()
    report = generator.generate_user_report("user123", {})
    report_id = report["report_id"]
    retrieved = generator.get_report(report_id)
    assert retrieved == report

def test_get_report_nonexistent():
    """Test getting non-existent report"""
    generator = ReportGenerator()
    assert generator.get_report("nonexistent") is None

def test_get_reports_by_type():
    """Test getting reports by type"""
    generator = ReportGenerator()
    generator.generate_user_report("user1", {})
    generator.generate_system_report({})
    generator.generate_user_report("user2", {})
    user_reports = generator.get_reports_by_type("user_activity")
    assert len(user_reports) == 2

def test_export_report_json():
    """Test exporting report as JSON"""
    generator = ReportGenerator()
    report = generator.generate_user_report("user123", {"test": "data"})
    json_str = generator.export_report_json(report["report_id"])
    assert json_str is not None
    parsed = json.loads(json_str)
    assert parsed["user_id"] == "user123"


def test_export_nonexistent_report():
    """Test exporting non-existent report"""
    generator = ReportGenerator()
    assert generator.export_report_json("nonexistent") is None
