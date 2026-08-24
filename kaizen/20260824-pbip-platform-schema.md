# PBIP platform schema

**Date**: 2026-08-24 | **Context**: apertura di `powerbi/CRM Demo.pbip` con Power BI Desktop

## What happened
Dopo la correzione del manifest, Desktop ha rifiutato `CRM Demo.Report/.platform` per uno
schema `$schema` non conforme al pattern Git Integration.

## Why it was wrong
I file `.platform` usavano `fabric/item/platformProperties/2.0.0`, mentre i progetti PBIP/PBIR
richiedono `fabric/gitIntegration/platformProperties/2.0.0/schema.json`.

## What to do instead
Usare lo schema Git Integration in `.platform` sia per Report sia per Semantic Model.
Validare il progetto con Power BI Desktop dopo ogni correzione del manifest o degli artifact.
