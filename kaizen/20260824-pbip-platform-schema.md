# PBIP platform schema

**Date**: 2026-08-24 | **Context**: apertura di `powerbi/CRM Demo.pbip` con Power BI Desktop

## What happened
Dopo la correzione del manifest, Desktop ha rifiutato `CRM Demo.Report/.platform` per uno
schema `$schema` non conforme al pattern Git Integration.

## Why it was wrong
I file `.platform` usavano inizialmente `fabric/item/platformProperties/2.0.0`; dopo il cambio di
URL, Desktop ha mostrato che `version` deve stare dentro `config`, non alla radice.

## What to do instead
Usare lo schema Git Integration in `.platform` sia per Report sia per Semantic Model, con
`config.version` e `config.logicalId` obbligatori.
Validare il progetto con Power BI Desktop dopo ogni correzione del manifest o degli artifact.

## Versioni metadata PBIR

I file `version.json` e `pages.json` sono metadata e richiedono rispettivamente gli schema
`versionMetadata/1.0.0` e `pagesMetadata/1.0.0`; gli schema `version/` e `pages/2.0.0` non sono
compatibili con il formato metadata richiesto da Power BI Desktop.

## Ulteriore correzione

`defaultPowerBIDataSourceVersion` non appartiene a `definition.pbism`; va mantenuta in
`definition/model.tmdl`. Il file `definition.pbism` contiene solo la versione del formato.
