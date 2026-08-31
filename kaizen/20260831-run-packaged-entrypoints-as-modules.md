# Run packaged entry points as modules

**Date**: 2026-08-31 | **Context**: Review Agent dispatcher invoking the vote publisher

## What happened

The dispatcher launched the publisher as a file path (`python scripts/review_vote_publish.py`). Python put the script directory on `sys.path` instead of the repository root, so `from scripts.github_app_auth import ...` raised `ModuleNotFoundError` and the vote was never published. The same run also showed the review clone lacked the pull request commit.

## Why it was wrong

Unit tests mocked the subprocess call, so the wiring was never exercised. Only a real end-to-end run touched the actual process boundary.

## What to do instead

Invoke internal entry points as modules (`-m package.module`) with the package root as working directory, and assert the command shape in a test. Prove cross-process wiring with one real smoke before declaring a chain operational.
