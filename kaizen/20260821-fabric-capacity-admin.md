# Fabric capacity authorization plane

**Date**: 2026-08-21 | **Context**: rail `branch_out` assegna un feature workspace alla capacity

## What happened
Il deploy SP aveva il ruolo Azure RBAC `Contributor` sulla risorsa capacity, ma Fabric ha restituito `forbidden` su `assignToCapacity`.

## Why it was wrong
Azure RBAC sulla risorsa e ruoli di amministrazione della capacity Fabric sono piani distinti di autorizzazione.

## What to do instead
Assegnare il deploy SP, direttamente o tramite gruppo Entra, come Capacity administrator nel portale Fabric.
Verificare il rail con un rerun prima di considerare il permesso effettivo.