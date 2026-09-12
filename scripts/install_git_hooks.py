#!/usr/bin/env python3
"""
Install local git hooks for Mutual Funds Tracker.
Sets up a pre-push hook that runs pytest locally before any push.
"""
import os
import stat
import sys

HOOK_CONTENT = """#!/bin/sh
# Pre-push hook: run regression test suite before pushing to remote
echo "=========================================================="
echo " Running Mutual Funds Tracker Regression Test Suite..."
echo "=========================================================="

python -m pytest tests/ -v

STATUS=$?

if [ $STATUS -ne 0 ]; then
    echo ""
    echo "❌ [PRE-PUSH REJECTED] Regression tests failed!"
    echo "Please fix the failing tests or run pytest locally before pushing."
    echo "=========================================================="
    exit 1
fi

echo ""
echo "✅ [PRE-PUSH PASSED] All regression tests passed successfully!"
echo "=========================================================="
exit 0
"""


def install_hooks():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_hooks_dir = os.path.join(repo_root, ".git", "hooks")

    if not os.path.exists(git_hooks_dir):
        print(f"Error: .git/hooks directory not found at {git_hooks_dir}")
        sys.exit(1)

    pre_push_path = os.path.join(git_hooks_dir, "pre-push")
    with open(pre_push_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HOOK_CONTENT)

    # Make executable on Unix/Git Bash
    st = os.stat(pre_push_path)
    os.chmod(pre_push_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(f"[OK] Successfully installed pre-push hook to {pre_push_path}")
    print("[INFO] Tests will now automatically run locally whenever you execute 'git push'.")



if __name__ == "__main__":
    install_hooks()
