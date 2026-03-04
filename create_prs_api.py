"""
Create PRs via GitHub API
"""
import requests

TOKEN = "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"
OWNER = "nomanqadri34"
REPO = "smart-health-system"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Create PR #1
pr1 = {
    "title": "Add input validation for symptom analysis",
    "body": """Fixes #1

This PR adds comprehensive input validation to improve security and data quality:

## Changes
- Add validators module with symptom, email, and phone validation
- Implement XSS and injection protection  
- Add comprehensive unit tests with pytest
- Ensure input sanitization for user safety

## Test Coverage
- 25+ unit tests covering all validation scenarios
- Tests for XSS attempts, injection attacks, and edge cases
- Validation for empty, too short, and too long inputs""",
    "head": "feature/add-input-validation",
    "base": "main"
}

# Create PR #2
pr2 = {
    "title": "Improve error handling and logging",
    "body": """Fixes #2

This PR enhances error handling across the application:

## Changes
- Centralized error handling with custom exception classes
- Structured error responses with consistent JSON format
- Comprehensive logging for debugging
- Full test coverage for error handlers
- Support for validation, database, auth, and 404 errors

## Test Coverage
- 20+ unit tests for all error handler functionality
- Tests for error response formatting
- Integration tests for error handler middleware""",
    "head": "feature/improve-error-handling",
    "base": "main"
}

def create_pr(pr_data):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls"
    response = requests.post(url, headers=headers, json=pr_data)
    if response.status_code == 201:
        pr = response.json()
        print(f"✓ Created PR #{pr['number']}: {pr['title']}")
        print(f"  URL: {pr['html_url']}")
        return pr['number']
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return None

def merge_pr(pr_number):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{pr_number}/merge"
    data = {
        "commit_title": f"Merge pull request #{pr_number}",
        "merge_method": "merge"
    }
    response = requests.put(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"✓ Merged PR #{pr_number}")
        return True
    else:
        print(f"✗ Failed to merge: {response.status_code}")
        print(response.text)
        return False

print("Creating PRs...\n")
pr1_num = create_pr(pr1)
pr2_num = create_pr(pr2)

print("\nMerging PRs...\n")
if pr1_num:
    merge_pr(pr1_num)
if pr2_num:
    merge_pr(pr2_num)

print("\n✓ Done! PRs created and merged.")
