"""
Create GitHub issues for F2P PRs
"""
import requests

TOKEN = "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"
OWNER = "nomanqadri34"
REPO = "smart-health-system"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

issues = [
    {
        "title": "Add notification system for appointments and alerts",
        "body": """## Problem
The application needs a notification system to send appointment reminders and alerts to users via email and SMS.

## Proposed Solution
Implement a comprehensive notification service with:
- Email notification support with SMTP
- SMS notification support with length validation
- Appointment reminder functionality
- Caching service for performance optimization

## Acceptance Criteria
- [ ] Email notifications with customizable templates
- [ ] SMS notifications with 160 character limit
- [ ] Appointment reminder system
- [ ] In-memory cache with TTL support
- [ ] Cache statistics and management
- [ ] Comprehensive unit tests (15+ tests)
- [ ] Integration with existing services

## Technical Requirements
- Support for multiple notification channels
- Proper error handling
- Test coverage > 90%
- Documentation
""",
        "labels": ["enhancement", "feature"]
    },
    {
        "title": "Add analytics and reporting system",
        "body": """## Problem
The application lacks analytics tracking and reporting capabilities to monitor user activity and system performance.

## Proposed Solution
Implement analytics and reporting system with:
- Event tracking with metadata
- User activity analytics
- System metrics collection
- Report generation and export

## Acceptance Criteria
- [ ] Event tracking system with timestamps
- [ ] User-specific event filtering
- [ ] Event type categorization
- [ ] Analytics summary generation
- [ ] User activity report generation
- [ ] System metrics reporting
- [ ] JSON report export
- [ ] Comprehensive unit tests (15+ tests)

## Technical Requirements
- Efficient event storage
- Fast querying and filtering
- Report export in multiple formats
- Test coverage > 90%
- Documentation
""",
        "labels": ["enhancement", "feature"]
    }
]

def create_issue(issue_data):
    """Create GitHub issue"""
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/issues"
    response = requests.post(url, headers=headers, json=issue_data)
    
    if response.status_code == 201:
        issue = response.json()
        print(f"[OK] Created issue #{issue['number']}: {issue['title']}")
        print(f"  URL: {issue['html_url']}")
        return issue['number']
    else:
        print(f"[FAIL] Failed to create issue: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("Creating GitHub Issues for F2P PRs")
    print("=" * 60)
    
    issue_numbers = []
    for i, issue_data in enumerate(issues, 1):
        print(f"\n[{i}/{len(issues)}] Creating issue...")
        issue_num = create_issue(issue_data)
        if issue_num:
            issue_numbers.append(issue_num)
    
    print("\n" + "=" * 60)
    print("[SUCCESS] All issues created!")
    print("=" * 60)
    print(f"\nCreated {len(issue_numbers)} issues:")
    for num in issue_numbers:
        print(f"  - Issue #{num}")
    
    print("\nNext steps:")
    print("  1. Run: python create_f2p_prs.py")
    print("  2. Verify: python verify_f2p.py")
    print("  3. Evaluate: cd repo_evaluator-main-new-2-no-llm")
    print(f"     python repo_evaluator.py {OWNER}/{REPO} --token {TOKEN}")
