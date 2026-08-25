# Permission probes must be invalid

**Date**: 2026-08-25 | **Context**: S0-07 Fabric permission verification

## What happened

A workspace creation probe used a valid request body and the Dev Agent SP created a real workspace.
The workspace was identified by its unique probe name and deleted immediately.

## Why it was wrong

A permission test must be denied by authorization before resource creation. A valid payload tests
both authorization and provisioning, which can create side effects when least privilege is absent.

## What to do instead

Use an intentionally invalid or non-executing request only when testing authorization, or use a
controlled disposable resource with explicit cleanup. Record HTTP status and never infer denial
from the intended purpose of a request.
