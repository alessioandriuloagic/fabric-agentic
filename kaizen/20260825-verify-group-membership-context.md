# Verify group membership in the right context

**Date**: 2026-08-25 | **Context**: S0-07 Fabric permission probe

## What happened

The CLI query reported zero members for `FabricAgentDeploy`, while the Entra portal showed
`fabric-agentic-dev-agent` as a direct member.

## Why it was wrong

A single Graph/CLI listing can be affected by tenant, permission, API consistency, or query
context. It must not override direct portal evidence without reconciling the discrepancy.

## What to do instead

Record the tenant and group object ID, verify the exact service principal Object ID in the portal
and Graph, and use the Fabric authorization probe as the final effective-permission check.
