"""
Add test framework configuration for F2P analysis
"""
import subprocess
import os

def add_pytest_to_requirements():
    """Add pytest to requirements.txt"""
    print("[1/4] Adding pytest to requirements.txt...")
    
    with open("backend/requirements.txt", "a") as f:
        f.write("\n# Testing framework\npytest>=7.0.0\npytest-cov>=4.0.0\n")
    
    print("[OK] pytest added to requirements.txt")

def create_pytest_ini():
    """Create pytest.ini configuration"""
    print("[2/4] Creating pytest.ini...")
    
    pytest_config = """[pytest]
testpaths = backend
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
"""
    
    with open("pytest.ini", "w") as f:
        f.write(pytest_config)
    
    print("[OK] pytest.ini created")

def create_conftest():
    """Create conftest.py for pytest"""
    print("[3/4] Creating backend/conftest.py...")
    
    conftest_content = '''"""
Pytest configuration and fixtures
"""
import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.dirname(__file__))
'''
    
    with open("backend/conftest.py", "w") as f:
        f.write(conftest_content)
    
    print("[OK] conftest.py created")

def create_github_workflow():
    """Create GitHub Actions workflow for CI"""
    print("[4/4] Creating .github/workflows/tests.yml...")
    
    # Create .github/workflows directory
    os.makedirs(".github/workflows", exist_ok=True)
    
    workflow_content = """name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r backend/requirements.txt
    
    - name: Run tests
      run: |
        pytest backend/ -v --cov=backend --cov-report=term
"""
    
    with open(".github/workflows/tests.yml", "w") as f:
        f.write(workflow_content)
    
    print("[OK] GitHub Actions workflow created")

def commit_and_push():
    """Commit and push changes"""
    print("\n[5/5] Committing and pushing changes...")
    
    commands = [
        "git add backend/requirements.txt pytest.ini backend/conftest.py .github/workflows/tests.yml",
        'git commit -m "Add pytest test framework and CI configuration"',
        "git push origin main"
    ]
    
    for cmd in commands:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[WARN] Command failed: {cmd}")
            print(result.stderr)
        else:
            print(f"[OK] {cmd}")

def main():
    """Add test framework configuration"""
    print("=" * 60)
    print("ADDING TEST FRAMEWORK FOR F2P ANALYSIS")
    print("=" * 60)
    print("\nThis will:")
    print("  1. Add pytest to requirements.txt")
    print("  2. Create pytest.ini configuration")
    print("  3. Create conftest.py for pytest")
    print("  4. Create GitHub Actions CI workflow")
    print("  5. Commit and push changes")
    
    input("\nPress Enter to continue...")
    
    try:
        add_pytest_to_requirements()
        create_pytest_ini()
        create_conftest()
        create_github_workflow()
        commit_and_push()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Test framework added!")
        print("=" * 60)
        print("\nChanges made:")
        print("  - Added pytest to backend/requirements.txt")
        print("  - Created pytest.ini configuration")
        print("  - Created backend/conftest.py")
        print("  - Created .github/workflows/tests.yml")
        print("\nNext steps:")
        print("  1. Install pytest: pip install pytest pytest-cov")
        print("  2. Run tests: pytest backend/ -v")
        print("  3. Re-run evaluator to see F2P analysis")
        
        return True
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        return False

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
