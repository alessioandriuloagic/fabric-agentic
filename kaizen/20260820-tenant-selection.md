# Tenant di esecuzione

**Date**: 2026-08-20 | **Context**: provisioning delle identità agentiche e della capacity Fabric

## What happened

La pianificazione iniziale presumeva il tenant Azure corrente per creare i service principal.
L'utente ha chiarito che identità e capacity Fabric risiedono nel tenant Agic Dev.

## Why it was wrong

Una credenziale OIDC deve essere registrata nel tenant che ospita la capacity e i workspace
Fabric; creare l'applicazione in un tenant diverso renderebbe impossibile l'esecuzione.

## What to do instead

Prima di creare identità, verificare esplicitamente tenant ID e subscription Agic Dev.
Usare quel tenant per ExecutionCredential e service principal; GitHub e Azure Boards restano
servizi esterni al perimetro Fabric.

Prima di associare Azure DevOps al tenant Agic Dev, distinguere l'identita' Member `agicdev` dalla
identita' federata `agic.it`, che resta Guest. Il cambio di directory deve essere eseguito usando
l'account Member Agic Dev, aggiunto all'organizzazione Azure DevOps e con ruolo Organization Owner;
non serve convertire l'identita' Guest `agic.it`.
