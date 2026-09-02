# Use explicit commits for branch recreation

**Date**: 2026-09-02 | **Context**: CRM preflight fix PR branch recreation

## What happened
After switching to a new branch based on `origin/main`, a reflog-relative commit expression selected an earlier, unrelated change and caused conflicts.

## Why it was wrong
Relative revision expressions depend on the branch currently checked out and are unsafe after a branch switch.

## What to do instead
Record the new commit SHA before switching branches. Cherry-pick that explicit SHA onto the fresh branch and abort immediately if another commit is selected.