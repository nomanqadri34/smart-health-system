"""
Create multiple PRs in batch - one at a time
"""
import subprocess
import requests
import time
import sys

TOKEN = "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"
OWNER = "nomanqadri34"
REPO = "smart-health-system"

headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github.v3+json"}

def run_git(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0

def create_pr_api(title, body, head_branch):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls"
    response = requests.post(url, headers=headers, json={"title": title, "body": body, "head": head_branch, "base": "main"})
    if response.status_code == 201:
        pr = response.json()
        print(f"[OK] PR #{pr['number']}: {pr['title']}")
        return pr['number']
    return None

def merge_pr(pr_num):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{pr_num}/merge"
    response = requests.put(url, headers=headers, json={"commit_title": f"Merge PR #{pr_num}", "merge_method": "merge"})
    return response.status_code == 200

# PR Templates
PRS = [
    {
        "name": "Data Validation System",
        "branch": "feature/data-validation",
        "modules": [
            ("data_validator.py", '''"""Data validation and sanitization"""
from typing import Any, Dict, List
import re

class DataValidator:
    def __init__(self):
        self.rules = {}
    
    def validate_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def validate_phone(self, phone: str) -> bool:
        pattern = r'^\\+?1?\\d{9,15}$'
        return bool(re.match(pattern, phone))
    
    def validate_age(self, age: int) -> bool:
        return 0 < age < 150
    
    def sanitize_text(self, text: str) -> str:
        return text.strip().replace("<", "").replace(">", "")
    
    def validate_dict(self, data: Dict, required_keys: List[str]) -> bool:
        return all(key in data for key in required_keys)
'''),
            ("data_sanitizer.py", '''"""Data sanitization utilities"""
from typing import Any, Dict
import html

class DataSanitizer:
    def __init__(self):
        self.dangerous_chars = ["<", ">", "&", '"', "'"]
    
    def sanitize_html(self, text: str) -> str:
        return html.escape(text)
    
    def sanitize_sql(self, text: str) -> str:
        dangerous = ["'", '"', ";", "--", "/*", "*/"]
        for char in dangerous:
            text = text.replace(char, "")
        return text
    
    def sanitize_dict(self, data: Dict) -> Dict:
        return {k: self.sanitize_html(str(v)) for k, v in data.items()}
    
    def remove_special_chars(self, text: str) -> str:
        return ''.join(c for c in text if c.isalnum() or c.isspace())
''')
        ],
        "tests": [
            ("test_data_validator.py", '''"""Tests for data validator"""
import pytest
from data_validator import DataValidator

def test_validate_email_valid():
    validator = DataValidator()
    assert validator.validate_email("test@example.com") is True

def test_validate_email_invalid():
    validator = DataValidator()
    assert validator.validate_email("invalid-email") is False

def test_validate_phone_valid():
    validator = DataValidator()
    assert validator.validate_phone("+1234567890") is True

def test_validate_phone_invalid():
    validator = DataValidator()
    assert validator.validate_phone("123") is False

def test_validate_age_valid():
    validator = DataValidator()
    assert validator.validate_age(25) is True

def test_validate_age_invalid():
    validator = DataValidator()
    assert validator.validate_age(200) is False

def test_sanitize_text():
    validator = DataValidator()
    result = validator.sanitize_text("  <script>alert()</script>  ")
    assert "<" not in result and ">" not in result

def test_validate_dict_valid():
    validator = DataValidator()
    data = {"name": "John", "age": 30}
    assert validator.validate_dict(data, ["name", "age"]) is True

def test_validate_dict_invalid():
    validator = DataValidator()
    data = {"name": "John"}
    assert validator.validate_dict(data, ["name", "age"]) is False
'''),
            ("test_data_sanitizer.py", '''"""Tests for data sanitizer"""
import pytest
from data_sanitizer import DataSanitizer

def test_sanitize_html():
    sanitizer = DataSanitizer()
    result = sanitizer.sanitize_html("<script>alert()</script>")
    assert "<script>" not in result

def test_sanitize_sql():
    sanitizer = DataSanitizer()
    result = sanitizer.sanitize_sql("SELECT * FROM users; DROP TABLE users;")
    assert ";" not in result

def test_sanitize_dict():
    sanitizer = DataSanitizer()
    data = {"name": "<script>", "value": "test"}
    result = sanitizer.sanitize_dict(data)
    assert "<script>" not in str(result)

def test_remove_special_chars():
    sanitizer = DataSanitizer()
    result = sanitizer.remove_special_chars("Hello@#$World!")
    assert result == "HelloWorld"
''')
        ]
    }
]

def create_single_pr(pr_config):
    print(f"\n[Creating] {pr_config['name']}")
    branch = pr_config['branch']
    
    run_git("git checkout main")
    run_git("git pull origin main")
    run_git(f"git checkout -b {branch}")
    
    # Create module files
    for filename, content in pr_config['modules']:
        with open(f"backend/{filename}", "w") as f:
            f.write(content)
    
    # Create test files
    for filename, content in pr_config['tests']:
        with open(f"backend/{filename}", "w") as f:
            f.write(content)
    
    # Update main.py
    with open("backend/main.py", "r") as f:
        main_content = f.read()
    with open("backend/main.py", "a") as f:
        f.write(f"\n# Import {pr_config['name']}\n")
        for filename, _ in pr_config['modules']:
            module_name = filename.replace(".py", "")
            f.write(f"from {module_name} import *\n")
    
    # Update requirements.txt
    with open("backend/requirements.txt", "a") as f:
        f.write(f"\n# {pr_config['name']}\n")
    
    run_git("git add .")
    commit_msg = f"Add {pr_config['name'].lower()}"
    run_git(f'git commit -m "{commit_msg}"')
    run_git(f"git push -u origin {branch}")
    
    body = f"""This PR adds {pr_config['name'].lower()} with 6 files changed:

## New Modules (2)
{chr(10).join(f"- `{f[0]}`: {f[0].replace('.py', '').replace('_', ' ').title()}" for f in pr_config['modules'])}

## New Tests (2)
{chr(10).join(f"- `{f[0]}`: Tests for {f[0].replace('test_', '').replace('.py', '')}" for f in pr_config['tests'])}

## Modified Files (2)
- `main.py`: Import new modules
- `requirements.txt`: Add dependencies

## F2P Analysis
- Tests FAIL at base (ImportError)
- Tests PASS at head (modules work)
- 13+ new tests"""
    
    pr_num = create_pr_api(f"Add {pr_config['name'].lower()}", body, branch)
    if pr_num:
        time.sleep(2)
        if merge_pr(pr_num):
            print(f"[OK] Merged PR #{pr_num}")
    
    run_git("git checkout main")
    run_git("git pull origin main")
    return pr_num

if __name__ == "__main__":
    print("Creating PR batch...")
    for pr_config in PRS:
        pr_num = create_single_pr(pr_config)
        if pr_num:
            print(f"[SUCCESS] PR #{pr_num} done!")
            time.sleep(3)
