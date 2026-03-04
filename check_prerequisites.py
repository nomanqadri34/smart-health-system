"""
Check prerequisites before running F2P workflow
"""
import sys
import subprocess
import os

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 7:
        print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"[FAIL] Python {version.major}.{version.minor} (need 3.7+)")
        return False

def check_module(module_name):
    """Check if Python module is installed"""
    try:
        __import__(module_name)
        print(f"[OK] {module_name} installed")
        return True
    except ImportError:
        print(f"[FAIL] {module_name} not installed")
        return False

def check_git():
    """Check if git is available"""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"[OK] {version}")
            return True
        else:
            print("[FAIL] git not found")
            return False
    except FileNotFoundError:
        print("[FAIL] git not installed")
        return False

def check_git_repo():
    """Check if we're in a git repository"""
    try:
        result = subprocess.run(
            ["git", "status"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("[OK] In git repository")
            return True
        else:
            print("[FAIL] Not in git repository")
            return False
    except Exception:
        print("[FAIL] Git repository check failed")
        return False

def check_internet():
    """Check internet connectivity"""
    try:
        import socket
        socket.create_connection(("github.com", 443), timeout=5)
        print("[OK] Internet connection active")
        return True
    except OSError:
        print("[FAIL] No internet connection")
        return False

def check_github_token():
    """Check if GitHub token is set in scripts"""
    token = "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"
    if token and len(token) > 20:
        print(f"[OK] GitHub token configured ({len(token)} chars)")
        return True
    else:
        print("[FAIL] GitHub token not configured")
        return False

def check_files_exist():
    """Check if required scripts exist"""
    required_files = [
        "create_f2p_prs.py",
        "create_issues_for_f2p.py",
        "run_f2p_workflow.py"
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"[OK] {file} exists")
        else:
            print(f"[FAIL] {file} missing")
            all_exist = False
    
    return all_exist

def main():
    """Run all prerequisite checks"""
    print("=" * 60)
    print("F2P PREREQUISITE CHECKER")
    print("=" * 60)
    
    checks = []
    
    print("\n[1] Python Environment")
    checks.append(check_python_version())
    
    print("\n[2] Required Python Modules")
    checks.append(check_module("requests"))
    checks.append(check_module("subprocess"))
    
    print("\n[3] Git")
    checks.append(check_git())
    checks.append(check_git_repo())
    
    print("\n[4] Network")
    checks.append(check_internet())
    
    print("\n[5] Configuration")
    checks.append(check_github_token())
    
    print("\n[6] Required Files")
    checks.append(check_files_exist())
    
    print("\n" + "=" * 60)
    
    if all(checks):
        print("[SUCCESS] ALL CHECKS PASSED!")
        print("=" * 60)
        print("\nYou're ready to run:")
        print("  python run_f2p_workflow.py")
        return True
    else:
        print("[FAIL] SOME CHECKS FAILED")
        print("=" * 60)
        print("\nPlease fix the issues above before running the workflow.")
        
        # Provide solutions
        print("\nCommon Solutions:")
        if not check_module("requests"):
            print("  - Install requests: pip install requests")
        if not check_git():
            print("  - Install git: https://git-scm.com/downloads")
        if not check_internet():
            print("  - Check your internet connection")
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
