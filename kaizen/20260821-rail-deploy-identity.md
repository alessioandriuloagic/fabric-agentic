# Rail deploy identity

**Date**: 2026-08-21 | **Context**: implementazione del rail `branch_out`

## What happened
Il workflow iniziale del rail usava le variabili OIDC del Dev Agent per creare workspace e assegnare capacity.

## Why it was wrong
Il Dev Agent deve restare senza scrittura Fabric; usare la sua identita' nella pipeline annulla la separazione dei privilegi.

## What to do instead
I rail usano sempre una federated credential OIDC dell'identita' di deploy, distinta dal Dev Agent.
Le variabili GitHub dell'environment identificano solo tale identita'; il Dev Agent puo' accodare il rail ma non impersonarla.