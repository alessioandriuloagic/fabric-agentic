# Distinguere condivisione e identita' della connection

**Date**: 2026-08-23 | **Context**: CRM run load e connection Dataverse

## What happened
La connection CRM era gia' condivisa con `fabric-agentic-deploy` come `User`, ma Spark ha restituito `Artifact Connection ... does not exist`.

## Why it was wrong
La condivisione autorizza l'uso dell'artifact, ma la connection mostrata usa credenziali OAuth 2.0 dell'utente proprietario. Non garantisce che un job eseguito da service principal possa ottenere un token delegato.

## What to do instead
Verificare sempre sia i destinatari della condivisione sia il tipo di identita' con cui la connection acquisisce le credenziali.
Per pipeline OIDC usare una connection con autenticazione app/service-principal compatibile, oppure un meccanismo server-to-server autorizzato; non basta assegnare il ruolo `User`.
