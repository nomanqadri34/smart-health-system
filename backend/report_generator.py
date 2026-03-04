"""
Report generation service
"""
from typing import Dict, List, Optional
from datetime import datetime
import json

class ReportGenerator:
    """Generate various reports"""
    
    def __init__(self):
        self.reports = []
    
    def generate_user_report(self, user_id: str, data: Dict) -> Dict:
        """Generate user activity report"""
        report = {
            "report_id": f"user_{user_id}_{datetime.now().timestamp()}",
            "type": "user_activity",
            "user_id": user_id,
            "generated_at": datetime.now().isoformat(),
            "data": data
        }
        self.reports.append(report)
        return report
    
    def generate_system_report(self, metrics: Dict) -> Dict:
        """Generate system metrics report"""
        report = {
            "report_id": f"system_{datetime.now().timestamp()}",
            "type": "system_metrics",
            "generated_at": datetime.now().isoformat(),
            "metrics": metrics
        }
        self.reports.append(report)
        return report
    
    def get_report(self, report_id: str) -> Optional[Dict]:
        """Get report by ID"""
        for report in self.reports:
            if report["report_id"] == report_id:
                return report
        return None
    
    def get_reports_by_type(self, report_type: str) -> List[Dict]:
        """Get all reports of specific type"""
        return [r for r in self.reports if r["type"] == report_type]
    
    def export_report_json(self, report_id: str) -> Optional[str]:
        """Export report as JSON string"""
        report = self.get_report(report_id)
        if report:
            return json.dumps(report, indent=2)
        return None
