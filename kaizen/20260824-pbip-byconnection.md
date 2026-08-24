# PBIP live semantic model binding

**Date**: 2026-08-24 | **Context**: collegamento del report CRM al modello Fabric remoto

## What happened
Il report usava `datasetReference.byPath`, che apre il semantic model locale in full edit mode.

## Why it was wrong
Per un modello già pubblicato in Fabric occorre `datasetReference.byConnection`, con la connection
string del workspace e l'ID del semantic model. `byPath` non rappresenta un collegamento live al
modello remoto.

## What to do instead
Usare `pbiServiceModelId`/`pbiModelDatabaseName` con l'ID del semantic model e il nome del workspace
Fabric nella connection string. Con `byConnection`, Desktop apre il report in live connection e
non apre il modello remoto in modifica.