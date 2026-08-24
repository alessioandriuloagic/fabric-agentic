# PBIR visual container minimum

**Date**: 2026-08-24 | **Context**: crash renderer `visualContainers` su report live-connected

## What happened
Il report con pagina PBIR valida ma senza visual containers falliva durante l'attivazione del
renderer Desktop con `Cannot read properties of undefined (reading 'visualContainers')`.

## Why it was wrong
Il validator strutturale accettava una pagina senza visuali, ma il renderer Desktop August 2026
non gestiva questo caso nel report live-connected.

## What to do instead
Mantenere almeno una visuale statica valida, ad esempio una textbox, prima di aprire il report.
Le visuali dati possono essere aggiunte dopo la verifica dei riferimenti al modello remoto.