# Guard tests must be hermetic

**Date**: 2026-08-31 | **Context**: Dev Agent `pre-push` main guard test

## What happened

The test asserted that `git push --dry-run origin HEAD:refs/heads/main` fails, but it ran against the ambient repository. Once the worktree sat on an up-to-date `main`, Git had nothing to push, skipped the `pre-push` hook and returned `0`, so the test failed even though the guard was intact.

## Why it was wrong

A security guard verified against ambient repository state proves nothing repeatable: it can pass when the guard is broken and fail when the guard works.

## What to do instead

Build a temporary bare remote and clone inside the test, create a real commit, then assert both directions: the forbidden ref is rejected and the allowed `feature/*` ref succeeds. Keep the probe offline and independent of the current branch.
