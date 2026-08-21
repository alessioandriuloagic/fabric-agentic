# Worktree command context

**Date**: 2026-08-21 | **Context**: S1-00 framework porting

## What happened
A branch command was initially run from the detached clean framework worktree instead of the Agentic repository.

## Why it was wrong
The clean source worktree is evidence for provenance and must not become the destination for Agentic changes.

## What to do instead
Use explicit `git -C <repository>` commands whenever source and destination worktrees are both active.
Keep the framework source detached at its recorded commit and create feature branches only in Agentic.