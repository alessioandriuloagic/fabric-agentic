# Distinguere connessione Git e visibilita' workspace

**Date**: 2026-08-26 | **Context**: `pipe_agent_sync_workspace`, run `32951020367`

## What happened
La schermata Fabric mostrava repository e branch corretti, ma il rail ha restituito
`workspace_id: null` e `bad_request`.

## Why it was wrong
La schermata prova la configurazione Git del workspace aperto dall'utente; non prova che
l'identita' OIDC usata dal workflow riesca a trovare quel workspace via API.

## What to do instead
Leggere prima `workspace_id` e `failure_stage` dal `rail-result.json`.
Solo se il workspace viene risolto si deve diagnosticare `git/status` o `updateFromGit`.