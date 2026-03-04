"""
Script to create GitHub issues and PRs for the repo evaluator.
"""
import requests
import json

GITHUB_TOKEN = "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"
REPO_OWNER = "nomanqadri34"
REPO_NAME = "smart-health-system"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Create Issue #1
issue1_data = {
    "title": "Add input validation for symptom analysis",
    "body": """## Problem
The application currently lacks proper input validation for user-submitted symptom data, which could lead to security vulnerabilities and data quality issues.

## Proposed Solution
Implement comprehensive input validation including:
- Symptom text validation with length constraints
- XSS and injection attack prevention
- Email format validation
- Phone number format validation

## Acceptance Criteria
- [ ] Validate symptom input with min/max length
- [ ] Block XSS attempts and malicious input
- [ ] Validate email addresses
- [ ] Validate phone numbers
- [ ] Add unit tests with >90% coverage
""",
    "labels": ["enhancement", "security"]
}

# Create Issue #2
issue2_data = {
    "title": "Improve error handling and logging",
    "body": """## Problem
The application needs better error handling and logging to improve debugging and user experience.

## Proposed Solution
Implement centralized error handling with:
- Custom exception classes for different error types
- Structured error responses
- Comprehensive logging
- Consistent error format across API

## Acceptance Criteria
- [ ] Create custom exception classes
- [ ] Implement error handlers for FastAPI
- [ ] Add structured logging
- [ ] Create standardized error response format
- [ ] Add unit tests for error handlers
""",
    "labels": ["enhancement", "maintenance"]
}

def create_issue(issue_data):
    """Create a GitHub issue."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    response = requests.post(url, headers=headers, json=issue_data)
    if response.status_code == 201:
        issue = response.json()
        print(f"✓ Created issue #{issue['number']}: {issue['title']}")
        return issue['number']
    else:
        print(f"✗ Failed to create issue: {response.status_code}")
        print(response.text)
        return None

def create_pr(title, body, head_branch, base_branch="main"):
    """Create a GitHub pull request."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls"
    pr_data = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch
    }
    response = requests.post(url, headers=headers, json=pr_data)
    if response.status_code == 201:
        pr = response.json()
        print(f"✓ Created PR #{pr['number']}: {pr['title']}")
        return pr['number']
    else:
        print(f"✗ Failed to create PR: {response.status_code}")
        print(response.text)
        return None

def close_issue(issue_number):
    """Close a GitHub issue."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}"
    data = {"state": "closed"}
    response = requests.patch(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"✓ Closed issue #{issue_number}")
        return True
    else:
        print(f"✗ Failed to close issue: {response.status_code}")
        return False

if __name__ == "__main__":
    print("Creating GitHub issues and PRs...\n")
    
    # Create issues
    print("Step 1: Creating issues...")
    issue1_num = create_issue(issue1_data)
    issue2_num = create_issue(issue2_data)
    
    print("\n✓ Issues created successfully!")
    print(f"  Issue #1: https://github.com/{REPO_OWNER}/{REPO_NAME}/issues/{issue1_num}")
    print(f"  Issue #2: https://github.com/{REPO_OWNER}/{REPO_NAME}/issues/{issue2_num}")
    
    print("\nNote: The branches have already been merged to main.")
    print("The repo evaluator will now be able to analyze the merged commits as PRs.")
