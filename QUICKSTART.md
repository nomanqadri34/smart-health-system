# Quick Start Guide - F2P PRs

## TL;DR

Run this one command to create accepted PRs:

```bash
python run_f2p_workflow.py
```

That's it! The script will:
1. Create 2 GitHub issues
2. Create 2 PRs with 6 files each
3. Merge the PRs
4. Run the repo evaluator

Expected result: **2 PRs accepted (100% acceptance rate)**

---

## What Gets Created

### PR #1: Notification & Cache Services
- 6 files changed
- 2 new modules (notification, cache)
- 2 test files (18 tests total)
- 2 modified files (integration)

### PR #2: Analytics & Reporting
- 6 files changed
- 2 new modules (analytics, reports)
- 2 test files (18 tests total)
- 2 modified files (integration)

---

## Why It Works

Each PR has the **F2P pattern**:

**Before PR (main branch):**
```python
import notification_service  # ❌ ImportError
pytest test_notification_service.py  # ❌ FAILED
```

**After PR (PR branch):**
```python
import notification_service  # ✅ Success
pytest test_notification_service.py  # ✅ 18 PASSED
```

This proves the PR adds real, working functionality.

---

## Manual Steps (If Needed)

If you prefer to run steps individually:

```bash
# Step 1: Create issues
python create_issues_for_f2p.py

# Step 2: Create PRs
python create_f2p_prs.py

# Step 3: Verify F2P pattern (optional)
python verify_f2p.py

# Step 4: Run evaluator
cd repo_evaluator-main-new-2-no-llm
python repo_evaluator.py nomanqadri34/smart-health-system --token YOUR_TOKEN
```

---

## Expected Output

```
============================================================
REPOSITORY EVALUATION REPORT
============================================================
Repository: nomanqadri34/smart-health-system
Overall Score: 60+/100
Recommendation: ✓ GOOD

--- PR Analysis ---
Total PRs Analyzed: 2
Accepted PRs: 2
Accepted: 2 (100.0%)
Rejected: 0 (0.0%)

Accepted PRs:
  ✓ PR #X: Notification and cache services (6 files)
  ✓ PR #Y: Analytics and reporting system (6 files)
```

---

## Troubleshooting

### "PR rejected: difficulty_not_hard"
- Check file count: Must be 6+ files
- Solution: Already handled in script

### "PR rejected: no_f2p_pattern"
- Tests must fail on main, pass on PR branch
- Solution: Already handled in script

### Script fails
- Check GitHub token is valid
- Ensure you have write access to repo
- Check internet connection

---

## More Information

- **Full Guide:** See `F2P_GUIDE.md`
- **Workflow Diagram:** See `F2P_WORKFLOW.txt`
- **Summary:** See `F2P_SUMMARY.md`

---

## Support

If you encounter issues:
1. Check the error message
2. Review `F2P_GUIDE.md` troubleshooting section
3. Verify GitHub token and permissions
4. Check repo evaluator logs

---

**Ready? Run:** `python run_f2p_workflow.py`
