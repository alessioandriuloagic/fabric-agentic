# Dispatcher session must use the isolated clone

**Date**: 2026-08-25 | **Context**: issue 72 notebook session

## What happened

A direct Claude invocation was launched from the primary repository instead of the configured clone.
The Dev Agent created an untracked implementation file on main.

## Why it was wrong

The dispatcher config's repository path does not change the shell's current directory for direct commands.
Without an explicit working directory, an agent can modify the primary checkout.

## What to do instead

Always invoke Claude from the isolated clone, or pass the clone as the subprocess working directory.
Before any session, verify the clone path and confirm the primary repository has no new files.
