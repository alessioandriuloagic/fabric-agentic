# Connector profiles are open, adapters are registered

**Date**: 2026-09-01 | **Context**: static onboarding connector selector

## What happened
The two adapters built for tests (`crm_dataverse` and `file`) became the only connector values
accepted by the product profile and UI.

## Why it was wrong
A delivery kit must describe databases, CRM, Business Central, SharePoint, Oracle, PostgreSQL and
future sources even before an executable adapter exists.

## What to do instead
Keep source technology open in the profile and require explicit capabilities for unknown types.
Treat the registry as the catalog of executable adapters, never as the product's source allowlist.