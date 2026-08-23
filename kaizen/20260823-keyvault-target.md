# Destinazione Key Vault confermata dall'owner

**Date**: 2026-08-23 | **Context**: provisioning Key Vault per CRM connection

## What happened
La prima proposta usava il resource group `rg-lumesialink-demo`, ma l'owner ha corretto esplicitamente la destinazione.

## Why it was wrong
Il resource group non rappresentava il perimetro del progetto Fabric Agentic e avrebbe creato una risorsa nel contesto sbagliato.

## What to do instead
Usare subscription `898b6a78-11dd-4e23-bf53-9e17f541d955`, resource group `alessio_dev`, regione `italynorth` e nome `kv-fabric-agentic-dev`.
Verificare sempre subscription e resource group insieme prima di creare risorse Azure.
