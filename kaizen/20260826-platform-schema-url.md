# Usare lo schema ufficiale dei file .platform

**Date**: 2026-08-26 | **Context**: errore Fabric Missing or corrupted system files

## What happened
L'aggiunta di `version: "2.0"` ai due artifact Power BI non ha risolto l'errore collettivo
su notebook, report e semantic model.

## Why it was wrong
Tutti i cinque `.platform` usavano un riferimento `$schema` non coerente con il formato V2
documentato da Fabric: `gitIntegration/.../schema.json` invece dello schema platform ufficiale.

## What to do instead
Usare `https://developer.microsoft.com/json-schemas/fabric/platform/platformProperties.json`
in ogni `.platform`, mantenendo `version: "2.0"` e il `logicalId` esistente.