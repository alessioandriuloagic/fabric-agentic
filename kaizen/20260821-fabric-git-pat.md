# Fabric Git connection PAT

**Date**: 2026-08-21 | **Context**: creazione della Configured Connection GitHub in Fabric

## What happened
La Configured Connection GitHub selezionata in Fabric richiede una Account key.

## Why it was wrong
La connessione custodisce una credenziale GitHub per operare sul repository; non e' configurabile con i soli identificativi del repository.

## What to do instead
Creare un fine-grained PAT limitato al repository, con Metadata in lettura e Contents in lettura/scrittura.
Inserirlo direttamente nella Account key di Fabric, mai in chat, GitHub variables o repository.