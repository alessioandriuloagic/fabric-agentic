# Issue dispatcher resta acceso

**Date**: 2026-09-04 | **Context**: manual Issue Agent versus operational runtime

## What happened
Ho chiarito che l'Issue Agent puo' essere usato in VS Code/chat, ma non ho esplicitato abbastanza che il dispatcher Issue resta parte del runtime operativo.

## Why it was wrong
La preparazione manuale del pacchetto aumenta il contesto disponibile, ma non sostituisce il presidio automatico a tre dispatcher: Issue, Dev e Review devono restare avviabili insieme.

## What to do instead
Documentare sempre i due livelli: VS Code/chat per lavorare il materiale grezzo, tre dispatcher accesi per la catena operativa. L'Issue dispatcher resta attivo anche quando il pacchetto nasce da una sessione manuale.