# Dispatcher isolation requires a clone

**Date**: 2026-08-25 | **Context**: first real GitHub dispatcher cycle

## What happened

The first attempt used a detached Git worktree for the Dev Agent session.
The dispatcher refresh failed because it unconditionally checks out `main`.

## Why it was wrong

A worktree cannot check out `main` while the primary checkout already owns that branch.
The current refresh contract is compatible with a separate clone, not a shared worktree.

## What to do instead

Use a separate clone for each isolated dispatcher runtime, or change
`refresh_clone` explicitly to support branch-aware worktrees before adopting them.
