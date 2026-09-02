# Interpret inclusive watermark runs correctly

**Date**: 2026-09-02 | **Context**: CRM accounts second live load for #158

## What happened
The second load reread five records with the confirmed watermark and was initially treated as a failed idempotency test.

## Why it was wrong
ADR-0012 requires inclusive extraction to prevent data loss at equal timestamps; idempotency is the unchanged Bronze state after merge, not an empty source batch.

## What to do instead
For an inclusive watermark, verify stable destination count, primary-key uniqueness, unchanged watermark, and no duplicate Bronze rows. Do not require `loaded_count` to be zero.