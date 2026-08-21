# Capacity administration membership

**Date**: 2026-08-21 | **Context**: `branch_out` ha ricevuto `forbidden` su `assignToCapacity`

## What happened
È stato dedotto che Azure RBAC `Contributor` non bastasse e servisse un ruolo Fabric Capacity administrator.

## Why it was wrong
Il progetto IP prova il pattern corretto: Collaboratore Azure RBAC e Object ID del deploy SP in `properties.administration.members` della capacity.

## What to do instead
Verificare entrambi i piani prima di cambiare ruoli: Collaboratore sulla risorsa e membership amministrativa interna della capacity.
Per `fabricalessiodev`, aggiungere il deploy object ID `db9d4adb-db6a-4238-8e75-c69d21b1b37e` preservando i membri esistenti.