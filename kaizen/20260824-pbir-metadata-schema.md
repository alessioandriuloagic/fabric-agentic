# PBIR metadata schema

**Date**: 2026-08-24 | **Context**: apertura di `powerbi/CRM Demo.pbip` con Power BI Desktop

## What happened
Desktop ha rifiutato `version.json` e `pages/pages.json` perché gli schema non corrispondevano
alle versioni metadata PBIR supportate.

## Why it was wrong
`version.json` e `pages.json` sono metadata, non oggetti report. Puntarli agli schema `version/`
o `pages/2.0.0` produce un mismatch tra schema e modello.

## What to do instead
Usare `versionMetadata/1.0.0` per `version.json` e `pagesMetadata/1.0.0` per `pages.json`.
La validazione locale deve risultare succeeded con zero errori e zero warning.