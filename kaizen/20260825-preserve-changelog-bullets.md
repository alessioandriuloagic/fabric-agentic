# Preserve existing changelog bullets

**Date**: 2026-08-25 | **Context**: S0-N1/S0-N2 backlog update

## What happened

A targeted changelog patch inserted a new bullet but accidentally removed the `-` marker from
neighboring existing entries.

## Why it was wrong

The content remained readable but the Keep a Changelog list structure was damaged, creating
unrelated documentation churn.

## What to do instead

Inspect the exact diff after every documentation patch. Preserve list markers and surrounding
entries, and repair formatting before committing.
