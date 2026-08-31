# Configuration must not carry OS-specific syntax

**Date**: 2026-08-31 | **Context**: Issue and Review dispatcher configuration files

## What happened

Dispatcher configuration used `%USERPROFILE%` for local paths. `os.path.expandvars` only expands that syntax on Windows, so on Linux CI the value stayed literal and the tests that asserted expansion failed.

## Why it was wrong

The kit is meant to be distributed to colleagues on different machines. A configuration file that only resolves on one operating system silently breaks portability, and unit tests written on that same operating system cannot reveal it.

## What to do instead

Expand both `%VAR%` and `$VAR` in one shared helper, fall back to the home directory for `USERPROFILE`/`HOME`, and keep the profile files free of platform-specific syntax. Run the portability-sensitive tests on the CI operating system, not only locally.
