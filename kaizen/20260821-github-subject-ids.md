# Subject OIDC GitHub con identificativi

**Date**: 2026-08-21 | **Context**: federated credential GitHub Actions in Entra ID

## What happened
Il wizard Microsoft per GitHub Actions genera un subject con Organization ID e Repository ID:
`repo:owner@<org-id>/repo@<repo-id>:environment:<environment>`.

## Why it matters
Il subject deve corrispondere esattamente al valore generato dal wizard; il formato standard senza ID non va sostituito manualmente in questa schermata.

## What to do instead
Usare `repo:alessioandriuloagic@218064009/fabric-agentic@1340835193:environment:dev`.
Gli ID sono configurati nei campi separati e anche nel subject calcolato dal portale.
