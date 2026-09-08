# Attachments devono essere nel remoto

**Date**: 2026-09-04 | **Context**: Issue Agent attachment visibility

## What happened
Ho descritto `attachments/<issue-number>/` senza distinguere chiaramente tra file locale e file visibile alla sessione isolata.

## Why it was wrong
Il dispatcher Issue prepara una clone dedicata con `fetch`, `checkout main` e `merge --ff-only origin/main`; un file presente solo nella working copy locale non entra in quella clone.

## What to do instead
Quando il materiale grezzo deve essere letto da Issue o Dev Agent, committarlo e pusharlo nel repository remoto su un percorso referenziato dalla issue. Se non deve entrare nel repo, riassumerlo nel body/commenti della issue o usare un canale esterno esplicitamente accessibile e non segreto.