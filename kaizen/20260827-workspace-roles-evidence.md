# Workspace roles must be checked in the workspace UI

**Date**: 2026-08-27 | **Context**: S0-07 Fabric permission verification

## What happened

A read-only API check ran under the human account and could not see the expected agent workspaces, so the agent-specific roles were reported as non-verifiable. The owner supplied workspace UI evidence showing Deploy as Contributor, Dev Agent as Viewer, and Review Agent absent.

## Why it was wrong

The human control-plane context is not evidence about service-principal membership. It can produce a false negative when the workspace inventory or tenant context differs from the agent configuration.

## What to do instead

Record workspace UI/IAM evidence separately for each identity and workspace. Keep role evidence distinct from runtime API probes: the former can close membership, while the latter is still required for write-denial behavior.
