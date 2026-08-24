# PBIR metadata schema

**Date**: 2026-08-24 | **Context**: apertura di `powerbi/CRM Demo.pbip` con Power BI Desktop

## What happened
Desktop ha rifiutato `version.json` e `pages/pages.json` perché gli schema non corrispondevano
alle versioni metadata PBIR supportate.

## Why it was wrong
`version.json` e `pages.json` sono metadata, non oggetti report. Puntarli agli schema `version/`
o `pages/2.0.0` produce un mismatch tra schema e modello.

## What to do instead
Il manifest `.pbip` deve includere lo schema `fabric/pbip/pbipProperties/1.0.0`; senza `$schema`
Desktop può usare il parser legacy e segnalare una minor version non supportata.
Usare `versionMetadata/1.0.0` per `version.json`, con contenuto `"version": "1.0.0"`, e
`pagesMetadata/1.0.0` per `pages.json`. La validazione locale deve risultare succeeded con zero
errori e zero warning.

## Versione shortcut PBIP

La build Desktop August 2026 segnala una minor version non supportata quando il manifest usa
`"version": "1.0.0"`. Il manifest shortcut viene portato a `"version": "1.0"`; questa è distinta
dalla versione PBIR `definition.pbir` (`4.0`) e da quella metadata dei file PBIR (`1.0.0`).
